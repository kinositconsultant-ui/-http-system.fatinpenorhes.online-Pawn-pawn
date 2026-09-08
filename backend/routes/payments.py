"""Payments router — CRUD + receipt PDF.

Extracted from server.py during the Phase-3 refactor (iter 76).
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deps import (
    db,
    new_id,
    utcnow_iso,
    COLLECTION_MAP,
    get_current_user,
    require_admin,
    require_module,
    write_audit,
)
from services import (
    _fetch_item,
    _recompute_contract_status,
    _decrypted_settings,
    render_pickup_message,
)
import whatsapp as wapp
from pdf_utils import build_receipt_pdf
from realtime import notify as rt_notify

router = APIRouter(tags=["payments"])


# =====================================================================
# Models
# =====================================================================
class PaymentIn(BaseModel):
    contract_id: str
    amount: float
    type: Literal[
        "full",
        "partial",
        "interest_only",
        "overdue_full",          # Loan + Interest + Penalty (full close-out)
        "overdue_interest_pen",  # Interest + Penalty (contract stays open)
        "overdue_penalty_only",  # Just clear penalty
        "disbursement",          # Loan money paid OUT to client at contract signing (informational)
    ]
    date: str  # YYYY-MM-DD
    notes: str = ""


# =====================================================================
# Helpers
# =====================================================================
async def _generate_receipt_number() -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"RCP-{year}-"
    last = await db.payments.find({"receipt_number": {"$regex": f"^{prefix}"}}) \
        .sort("receipt_number", -1).limit(1).to_list(1)
    if last:
        try:
            seq = int(last[0]["receipt_number"].split("-")[-1]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


# =====================================================================
# Endpoints
# =====================================================================
@router.get("/payments")
async def list_payments(contract_id: Optional[str] = None, _: dict = Depends(require_module("payments"))):
    q = {"contract_id": contract_id} if contract_id else {}
    items = await db.payments.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@router.post("/payments")
async def create_payment(payload: PaymentIn, user: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if payload.date and payload.date < contract.get("contract_date", payload.date):
        raise HTTPException(status_code=400, detail="Payment date is before contract start date")
    receipt_number = await _generate_receipt_number()
    doc = payload.model_dump()
    doc["id"] = new_id()
    doc["receipt_number"] = receipt_number
    doc["created_at"] = utcnow_iso()
    await db.payments.insert_one(doc)
    was_redeemed = contract.get("status") == "redeemed"
    updated = await _recompute_contract_status(contract)
    newly_redeemed = updated["status"] == "redeemed" and not was_redeemed
    if updated["status"] == "redeemed":
        # Money is settled; the item now waits for physical hand-over (warehouse release).
        await db[COLLECTION_MAP[contract["item_type"]]].update_one(
            {"id": contract["item_id"]},
            {"$set": {"status": "redeemed"}},
        )
        if newly_redeemed:
            await db.contracts.update_one(
                {"id": contract["id"]},
                {"$set": {"redeemed_at": utcnow_iso(), "item_released": False}},
            )
    await write_audit(user, "create", "payment", doc["id"], {
        "receipt_number": receipt_number,
        "amount": doc["amount"],
        "contract_id": doc["contract_id"],
    })
    doc.pop("_id", None)
    rt_notify("payment.created", {"contract_id": doc["contract_id"], "amount": doc["amount"]})
    if newly_redeemed:
        rt_notify("contract.redeemed", {
            "contract_id": contract["id"],
            "contract_number": contract.get("contract_number"),
            "item_type": contract.get("item_type"),
        })
        pickup = await _send_pickup_ready_whatsapp(contract, user)
        return {"payment": doc, "contract": updated, "pickup_notification": pickup}
    return {"payment": doc, "contract": updated}


async def _send_pickup_ready_whatsapp(contract: dict, actor: dict, *, force: bool = False, template: str = "pickup_ready") -> dict:
    """Tell the client their loan is settled and the item is ready for collection. Never blocks the payment."""
    settings = await _decrypted_settings()
    if not force and settings.get("pickup_notify_enabled", True) is False:
        return {"status": "disabled", "reason": "Pickup notifications are switched off in Settings"}
    client_doc = await db.clients.find_one({"id": contract.get("client_id")}, {"_id": 0}) or {}
    phone = (client_doc.get("phone") or "").strip()
    if not phone:
        return {"status": "skipped", "reason": "Client has no phone number"}
    name = client_doc.get("full_name") or "Kliente"
    cnum = contract.get("contract_number", "")
    body = render_pickup_message(settings, name, cnum, contract.get("item_type"))
    try:
        result = await wapp.send_text(phone, body, settings)
    except Exception as exc:  # network / config errors must not fail the payment
        result = {"status": "failed", "error": str(exc)}
    await db.whatsapp_log.insert_one({
        "id": new_id(),
        "contract_id": contract["id"],
        "contract_number": cnum,
        "client_id": client_doc.get("id"),
        "client_phone": phone,
        "language": "tet+en",
        "template": template,
        "parameters": [name, cnum],
        "body": body,
        "result": result,
        "meta_message_id": result.get("meta_message_id"),
        "delivery_status": result.get("status") or "queued",
        "sent_at": result.get("sent_at"),
        "actor_id": actor.get("id"),
        "created_at": utcnow_iso(),
    })
    await write_audit(actor, f"whatsapp_{template}", "contract", contract["id"],
                      {"contract_number": cnum, "to": phone, "result_status": result.get("status")})
    return {"status": result.get("status"), "to": phone}


@router.get("/payments/{pid}/pdf")
async def payment_pdf(pid: str, lang: str = "en", _: dict = Depends(get_current_user)):
    p = await db.payments.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    c = await db.contracts.find_one({"id": p["contract_id"]}, {"_id": 0}) or {}
    c = await _recompute_contract_status(c) if c else {}
    client_doc = await db.clients.find_one({"id": c.get("client_id")}, {"_id": 0}) or {}
    item_doc = {}
    if c.get("item_type") and c.get("item_id"):
        item_doc = await _fetch_item(c["item_type"], c["item_id"]) or {}
    pdf_bytes = build_receipt_pdf(
        p, c, client_doc, c.get("remaining_balance", 0), item=item_doc,
        language=(lang or "en").lower(),
    )
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{p["receipt_number"]}.pdf"'},
    )


@router.delete("/payments/{pid}")
async def delete_payment(pid: str, user: dict = Depends(require_admin)):
    """Admin-only: delete a payment record."""
    payment = await db.payments.find_one({"id": pid}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    res = await db.payments.delete_one({"id": pid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Payment not found")
    contract = await db.contracts.find_one({"id": payment.get("contract_id")}, {"_id": 0})
    if contract:
        was_redeemed = contract.get("status") == "redeemed"
        already_released = bool(contract.get("item_released"))
        updated = await _recompute_contract_status(contract)
        # Un-redeemed by the deletion: put the item back under pawn so counts stay consistent.
        if was_redeemed and updated["status"] != "redeemed" and not already_released:
            await db[COLLECTION_MAP[contract["item_type"]]].update_one(
                {"id": contract["item_id"], "status": "redeemed"},
                {"$set": {"status": "pawned"}},
            )
            await db.contracts.update_one({"id": contract["id"]}, {"$unset": {"redeemed_at": "", "item_released": ""}})
    await write_audit(user, "delete", "payment", pid, {
        "receipt_number": payment.get("receipt_number"),
        "amount": payment.get("amount"),
        "type": payment.get("type"),
        "contract_id": payment.get("contract_id"),
    })
    return {"ok": True}
