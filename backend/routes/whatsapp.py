"""WhatsApp + daily reminder endpoints — send, preview, ad-hoc send, test, logs.

Extracted from server.py during Phase 2 refactor.
"""
from __future__ import annotations

import os
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, Query, Request
from fastapi.responses import PlainTextResponse
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

logger = logging.getLogger("fatin.whatsapp")

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
        "meta_message_id": result.get("meta_message_id"),
        "delivery_status": result.get("status") or "queued",
        "sent_at": result.get("sent_at"),
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



# =====================================================================
# Meta Cloud API delivery-status webhook (iter 58)
# =====================================================================
# GET  /whatsapp/webhook  → Meta subscription handshake (hub.mode/token/challenge)
# POST /whatsapp/webhook  → status callbacks: sent/delivered/read/failed
#
# Each status update carries `id` = the wamid returned when the message was
# originally sent. We stored that on the whatsapp_log row inside `result`
# (`result.meta_message_id`). We update the log row(s) with a top-level
# `delivery_status` + `delivery_updated_at` and a per-status timestamp
# (`sent_at` / `delivered_at` / `read_at` / `failed_at`) so the Contracts UI
# can render a pill without recomputing history.
# ---------------------------------------------------------------------
_STATUS_ORDER = {"queued": 0, "mocked": 0, "sent": 1, "delivered": 2, "read": 3, "failed": 9}


async def _meta_app_secret() -> bytes:
    s = await get_settings_doc()
    secret = (s.get("whatsapp_app_secret") or os.environ.get("WHATSAPP_APP_SECRET") or "").strip()
    return secret.encode("utf-8")


async def _meta_verify_token() -> str:
    s = await get_settings_doc()
    return (s.get("whatsapp_verify_token") or os.environ.get("WHATSAPP_VERIFY_TOKEN") or "").strip()


async def _apply_status_update(meta_message_id: str, new_status: str, ts: str) -> int:
    """Idempotent: only advance status forward (sent → delivered → read).
    Returns the number of whatsapp_log rows updated (0 if the message is
    unknown to us — Meta occasionally emits statuses for messages we never
    sent, e.g. echoes from another instance)."""
    if not meta_message_id:
        return 0
    # Locate every log row that references this wamid, including old rows
    # nested under `result.meta_message_id`.
    query = {
        "$or": [
            {"result.meta_message_id": meta_message_id},
            {"meta_message_id": meta_message_id},
        ]
    }
    stamp_field = {
        "sent": "sent_at",
        "delivered": "delivered_at",
        "read": "read_at",
        "failed": "failed_at",
    }.get(new_status)
    order_new = _STATUS_ORDER.get(new_status, 0)
    updated = 0
    async for row in db.whatsapp_log.find(query):
        current = row.get("delivery_status") or "queued"
        order_cur = _STATUS_ORDER.get(current, 0)
        # `failed` always applies; otherwise only move forward.
        if new_status != "failed" and order_new <= order_cur:
            if stamp_field and not row.get(stamp_field):
                await db.whatsapp_log.update_one(
                    {"_id": row["_id"]}, {"$set": {stamp_field: ts}}
                )
            continue
        set_doc = {"delivery_status": new_status, "delivery_updated_at": ts}
        if stamp_field:
            set_doc[stamp_field] = ts
        await db.whatsapp_log.update_one({"_id": row["_id"]}, {"$set": set_doc})
        updated += 1
    return updated


async def _process_meta_payload(payload: dict) -> dict:
    stats = {"statuses": 0, "updated": 0, "unknown": 0}
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            for st in value.get("statuses", []) or []:
                stats["statuses"] += 1
                wamid = st.get("id") or ""
                status = (st.get("status") or "").lower()
                ts_raw = st.get("timestamp")
                try:
                    ts_iso = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc).isoformat() \
                        if ts_raw else utcnow_iso()
                except Exception:
                    ts_iso = utcnow_iso()
                n = await _apply_status_update(wamid, status, ts_iso)
                if n:
                    stats["updated"] += n
                else:
                    stats["unknown"] += 1
                    # Keep an audit trail of orphan statuses for later investigation.
                    try:
                        await db.whatsapp_webhook_orphans.insert_one({
                            "id": new_id(),
                            "meta_message_id": wamid,
                            "status": status,
                            "raw": st,
                            "created_at": utcnow_iso(),
                        })
                    except Exception:
                        pass
    return stats


@router.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(request: Request):
    """Meta subscription handshake: echoes `hub.challenge` when the verify token matches."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge") or ""
    expected = await _meta_verify_token()
    if not expected:
        raise HTTPException(status_code=503, detail="Verify token not configured yet")
    if mode == "subscribe" and hmac.compare_digest(token or "", expected):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp/webhook")
async def whatsapp_webhook_receive(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
):
    """Receive Meta status callbacks. Signature-validated when app_secret is configured."""
    raw = await request.body()
    secret = await _meta_app_secret()
    if secret:
        # Enforce HMAC when we've been given an app secret; otherwise accept
        # (staging without Meta connected).
        if not x_hub_signature_256:
            raise HTTPException(status_code=400, detail="Missing signature header")
        expected = hmac.new(secret, raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(f"sha256={expected}", x_hub_signature_256):
            logger.warning("[whatsapp webhook] signature mismatch")
            raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    # Persist raw event first so nothing is lost if processing fails.
    try:
        await db.whatsapp_webhook_events.insert_one({
            "id": new_id(),
            "raw": payload,
            "received_at": utcnow_iso(),
        })
    except Exception:
        logger.exception("[whatsapp webhook] failed to persist raw event")
    background_tasks.add_task(_process_meta_payload, payload)
    return {"ok": True}


@router.get("/whatsapp/webhook-config")
async def whatsapp_webhook_config(_: dict = Depends(require_admin)):
    """Admin summary — is verify_token and app_secret configured?"""
    s = await get_settings_doc()
    verify = bool((s.get("whatsapp_verify_token") or os.environ.get("WHATSAPP_VERIFY_TOKEN")))
    secret = bool((s.get("whatsapp_app_secret") or os.environ.get("WHATSAPP_APP_SECRET")))
    orphan_count = await db.whatsapp_webhook_orphans.count_documents({})
    event_count = await db.whatsapp_webhook_events.count_documents({})
    return {
        "verify_token_configured": verify,
        "app_secret_configured": secret,
        "webhook_events_seen": event_count,
        "orphan_statuses": orphan_count,
    }


@router.get("/whatsapp/status/{contract_id}")
async def whatsapp_status_for_contract(contract_id: str, _: dict = Depends(get_current_user)):
    """Latest WhatsApp reminder delivery summary for one contract.

    Returns the most recent whatsapp_log row for this contract with a
    normalised `delivery_status` = queued | mocked | sent | delivered | read | failed.
    """
    row = await db.whatsapp_log.find_one(
        {"contract_id": contract_id},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not row:
        return {"contract_id": contract_id, "delivery_status": None}
    result = row.get("result") or {}
    fallback = row.get("delivery_status") or result.get("status") or "queued"
    return {
        "contract_id": contract_id,
        "delivery_status": fallback,
        "meta_message_id": row.get("meta_message_id") or result.get("meta_message_id"),
        "sent_at": row.get("sent_at") or result.get("sent_at"),
        "delivered_at": row.get("delivered_at"),
        "read_at": row.get("read_at"),
        "failed_at": row.get("failed_at"),
        "created_at": row.get("created_at"),
    }


@router.get("/whatsapp/status")
async def whatsapp_status_bulk(
    contract_ids: str = Query("", description="Comma-separated contract IDs; empty = latest per contract"),
    _: dict = Depends(get_current_user),
):
    """Batch version — returns {contract_id: {delivery_status, ...}} for the
    Contracts overdue table so it can render pills in a single request."""
    ids = [x for x in (contract_ids or "").split(",") if x]
    match = {"contract_id": {"$in": ids}} if ids else {}
    pipeline = [
        {"$match": match} if match else {"$match": {"contract_id": {"$ne": None}}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$contract_id",
            "doc": {"$first": "$$ROOT"},
        }},
    ]
    out: dict[str, dict] = {}
    async for row in db.whatsapp_log.aggregate(pipeline):
        d = row.get("doc") or {}
        result = d.get("result") or {}
        cid = d.get("contract_id")
        if not cid:
            continue
        out[cid] = {
            "delivery_status": d.get("delivery_status") or result.get("status") or "queued",
            "meta_message_id": d.get("meta_message_id") or result.get("meta_message_id"),
            "sent_at": d.get("sent_at") or result.get("sent_at"),
            "delivered_at": d.get("delivered_at"),
            "read_at": d.get("read_at"),
            "failed_at": d.get("failed_at"),
            "created_at": d.get("created_at"),
        }
    return out
