"""WhatsApp + daily reminder endpoints — send, preview, ad-hoc send, test, logs.

Extracted from server.py during Phase 2 refactor.
"""
from __future__ import annotations

from datetime import datetime, timezone, date, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from deps import (
    db,
    new_id,
    utcnow_iso,
    get_current_user,
    require_admin,
    require_not_cashier,
    write_audit,
)
from services import (
    _recompute_contract_status,
    _decrypted_settings,
    _send_reminder_for_contract,
    get_settings_doc,
)
import whatsapp as wapp

router = APIRouter()

# =====================================================================
class WhatsAppSendIn(BaseModel):
    contract_id: str
    language: Literal["en", "tet"] = "en"
    extra: Optional[str] = None



@router.post("/whatsapp/send")
async def whatsapp_send(payload: WhatsAppSendIn, user: dict = Depends(get_current_user)):
    c = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    c = await _recompute_contract_status(c)
    settings = await _decrypted_settings()
    result = await _send_reminder_for_contract(c, payload.language, settings, user)
    await write_audit(user, "whatsapp_send", "contract", c["id"], {"result_status": result.get("status")})
    return result


class WhatsAppPreviewIn(BaseModel):
    contract_id: str
    language: Literal["en", "tet"] = "en"


@router.post("/whatsapp/preview")
async def whatsapp_preview(payload: WhatsAppPreviewIn, user: dict = Depends(get_current_user)):
    """Return the rendered ad-hoc WhatsApp reminder body (Rule A math) without sending.

    Used by the Contracts UI "Preview & Send" modal so the cashier can review /
    edit the message before it goes out.
    """
    from reminders import build_reminder_body
    c = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    c = await _recompute_contract_status(c)
    client_doc = await db.clients.find_one({"id": c["client_id"]}, {"_id": 0}) or {}
    info = build_reminder_body(c, client_doc.get("full_name", ""), payload.language)
    info.update({
        "phone": client_doc.get("phone", ""),
        "client_name": client_doc.get("full_name", ""),
        "contract_number": c.get("contract_number", ""),
    })
    return info


class WhatsAppAdhocSendIn(BaseModel):
    contract_id: str
    language: Literal["en", "tet"] = "en"
    body: str
    to_phone: Optional[str] = None


@router.post("/whatsapp/adhoc-send")
async def whatsapp_adhoc_send(payload: WhatsAppAdhocSendIn, user: dict = Depends(get_current_user)):
    """Send a free-form (optionally edited) WhatsApp reminder body to the client.

    The frontend calls /whatsapp/preview first to get the templated Rule A math body,
    optionally edits it, then posts it back here to actually send via Meta Cloud API.
    Falls back to `mocked` when WhatsApp isn't configured.
    """
    c = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    client_doc = await db.clients.find_one({"id": c["client_id"]}, {"_id": 0}) or {}
    phone = (payload.to_phone or client_doc.get("phone") or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Client has no phone number")
    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message body is empty")
    settings = await _decrypted_settings()
    result = await wapp.send_text(phone, body, settings)
    await db.whatsapp_log.insert_one({
        "id": new_id(),
        "contract_id": c["id"],
        "contract_number": c.get("contract_number", ""),
        "client_id": client_doc.get("id"),
        "client_phone": phone,
        "language": payload.language,
        "template": "adhoc_text",
        "parameters": [],
        "body": body,
        "result": result,
        "actor_id": user.get("id"),
        "created_at": utcnow_iso(),
    })
    await write_audit(user, "whatsapp_adhoc_send", "contract", c["id"], {"result_status": result.get("status")})
    return result


@router.post("/whatsapp/reminders/run")
async def whatsapp_reminders_run(language: str = Query("en"), user: dict = Depends(require_not_cashier)):
    """Send reminders to all contracts due in N days or overdue (not yet redeemed/auctioned)."""
    settings = await _decrypted_settings()
    days_before = int(settings.get("reminder_days_before", 3))
    today = date.today()
    target_due = (today + timedelta(days=days_before)).isoformat()
    today_iso = today.isoformat()
    contracts = await db.contracts.find(
        {"status": {"$in": ["active", "overdue", "grace_period"]}},
        {"_id": 0},
    ).to_list(5000)
    sent: list[dict] = []
    for c in contracts:
        c = await _recompute_contract_status(c)
        due = c.get("due_date", "")
        if due <= target_due or due < today_iso:
            r = await _send_reminder_for_contract(c, language, settings, user)
            sent.append({"contract_number": c.get("contract_number"), "result": r.get("status")})
    return {"count": len(sent), "sent": sent}


class WhatsAppTestIn(BaseModel):
    to_phone: str
    body: str = ""


@router.post("/whatsapp/test")
async def whatsapp_test(payload: WhatsAppTestIn, admin: dict = Depends(require_admin)):
    """Send a free-form text WhatsApp message to verify Meta API credentials.

    NOTE: Meta only allows free-form text inside the 24-hour service window.
    For a brand-new conversation, you must send a template message first.
    """
    from whatsapp import send_text
    settings = await _decrypted_settings()
    if not (settings.get("whatsapp_token") and settings.get("whatsapp_phone_id")):
        raise HTTPException(status_code=400, detail="WhatsApp not configured. Save Phone Number ID and Access Token first.")
    body = payload.body.strip() or "✅ Test message from Fatin Penhores — Meta WhatsApp Cloud API is connected."
    result = await send_text(payload.to_phone, body, settings)
    await db.whatsapp_log.insert_one({
        "contract_id": None,
        "to": result.get("to"),
        "template": "(text test)",
        "language": "en",
        "parameters": [body[:200]],
        "status": result.get("status"),
        "meta_message_id": result.get("meta_message_id"),
        "error": result.get("error"),
        "raw": result,
        "created_at": utcnow_iso(),
    })
    await write_audit(admin, "whatsapp_test", "settings", "whatsapp", {"to": result.get("to"), "status": result.get("status")})
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/whatsapp/logs")
async def whatsapp_logs(_: dict = Depends(get_current_user)):
    return await db.whatsapp_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


# =====================================================================
# Daily overdue reminders (iter17) — admin management + manual trigger
# =====================================================================
@router.get("/reminders/status")
async def reminders_status(_: dict = Depends(require_admin)):
    """Overview for Settings UI — enabled flag, last-run stats, next scheduled run."""
    from scheduler import next_run_info
    s = await get_settings_doc()
    info = next_run_info()
    return {
        "enabled": bool(s.get("reminders_enabled", True)),
        "last_run_at": s.get("reminders_last_run_at"),
        "last_run_summary": s.get("reminders_last_run_summary", {}),
        "next_run_at": info.get("next_reminders_run_at"),
        "reminder_days": [1, 7, 9],
        "local_time": "09:00 Timor (UTC+9)",
    }


@router.post("/reminders/run")
async def reminders_run_now(admin: dict = Depends(require_admin)):
    """Manually trigger the daily reminder job. Returns the send summary."""
    from reminders import run_daily_reminders
    result = await run_daily_reminders()
    await write_audit(admin, "run_reminders", "reminders", None, result)
    return result


@router.get("/reminders/logs")
async def reminders_logs(_: dict = Depends(require_admin)):
    """Return the last 90 days of reminder attempts, capped at 500 rows."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    return await db.reminder_log.find(
        {"created_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("created_at", -1).limit(500).to_list(500)

