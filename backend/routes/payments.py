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
)
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
    updated = await _recompute_contract_status(contract)
    if updated["status"] == "redeemed":
        await db[COLLECTION_MAP[contract["item_type"]]].update_one(
            {"id": contract["item_id"]},
            {"$set": {"status": "redeemed"}},
        )
    await write_audit(user, "create", "payment", doc["id"], {
        "receipt_number": receipt_number,
        "amount": doc["amount"],
        "contract_id": doc["contract_id"],
    })
    doc.pop("_id", None)
    rt_notify("payment.created", {"contract_id": doc["contract_id"], "amount": doc["amount"]})
    return {"payment": doc, "contract": updated}


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
        await _recompute_contract_status(contract)
    await write_audit(user, "delete", "payment", pid, {
        "receipt_number": payment.get("receipt_number"),
        "amount": payment.get("amount"),
        "type": payment.get("type"),
        "contract_id": payment.get("contract_id"),
    })
    return {"ok": True}
