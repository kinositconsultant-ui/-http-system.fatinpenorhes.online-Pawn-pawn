"""Inspection Expenses (iter 60).

Owner: FATIN PENHORES

Tracks money the shop spends to inspect, service, or repair a pawned item
before or during a contract (radiator, oil, fuel, battery, lubricant, spare
parts, etc.). Each expense is:

  * Tied to a specific contract (which pins it to a client + item).
  * Recorded as a **cash outflow** when incurred.
  * Optionally later reimbursed by the client — that reimbursement is a
    **cash inflow** and is added to Cash on Hand.

Nothing here touches profit — this is purely operational cash flow. The
Finance page treats reimbursement-net cost as an "operating expense".
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from deps import (
    db,
    new_id,
    utcnow_iso,
    get_current_user,
    require_admin,
    require_not_cashier,
    write_audit,
)
from realtime import notify as rt_notify

router = APIRouter(tags=["inspections"])

INSPECTION_CATEGORIES = Literal[
    "radiator", "oil", "fuel", "battery", "lubricant",
    "spare_part", "labor", "other",
]


class InspectionIn(BaseModel):
    contract_id: str = Field(..., description="Contract this expense belongs to")
    category: INSPECTION_CATEGORIES = "other"
    description: str = ""
    amount: float
    incurred_date: str = ""  # ISO YYYY-MM-DD; empty = today
    notes: str = ""


class InspectionReimburseIn(BaseModel):
    reimbursed_amount: float
    reimbursed_date: str = ""  # ISO date; empty = today


async def _load_contract_meta(contract_id: str) -> dict:
    """Fetch minimal contract meta and item info so we can denormalize
    it onto the expense row for fast list rendering."""
    contract = await db.contracts.find_one(
        {"id": contract_id},
        {"_id": 0, "id": 1, "contract_number": 1, "client_id": 1,
         "item_type": 1, "item_id": 1},
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@router.get("/inspections")
async def list_inspections(
    contract_id: Optional[str] = Query(None),
    reimbursed: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
    _: dict = Depends(get_current_user),
):
    q: dict = {}
    if contract_id:
        q["contract_id"] = contract_id
    if reimbursed is not None:
        q["reimbursed"] = reimbursed
    if category:
        q["category"] = category
    rows = await db.inspections.find(q, {"_id": 0}).sort("incurred_date", -1).to_list(5000)
    return rows


@router.post("/inspections")
async def create_inspection(
    payload: InspectionIn,
    user: dict = Depends(require_not_cashier),
):
    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive")
    contract = await _load_contract_meta(payload.contract_id)
    doc = {
        "id": new_id(),
        "contract_id": payload.contract_id,
        "contract_number": contract.get("contract_number", ""),
        "client_id": contract.get("client_id"),
        "item_type": contract.get("item_type"),
        "item_id": contract.get("item_id"),
        "category": payload.category,
        "description": payload.description,
        "amount": round(float(payload.amount), 2),
        "incurred_date": payload.incurred_date or date.today().isoformat(),
        "notes": payload.notes,
        "reimbursed": False,
        "reimbursed_amount": 0.0,
        "reimbursed_date": "",
        "created_by": user.get("id"),
        "created_at": utcnow_iso(),
    }
    await db.inspections.insert_one(doc)
    await write_audit(
        user, "create", "inspection", doc["id"],
        {"contract_number": doc["contract_number"], "category": doc["category"],
         "amount": doc["amount"]},
    )
    doc.pop("_id", None)
    return doc


@router.get("/inspections/summary")
async def inspection_summary(_: dict = Depends(get_current_user)):
    """Cheap aggregation used by Finance and the Inspections page header."""
    incurred_total = 0.0
    reimbursed_total = 0.0
    pending_count = 0
    by_category: dict[str, dict] = {}
    async for r in db.inspections.find({}, {"_id": 0}):
        amt = float(r.get("amount", 0) or 0)
        reimb = float(r.get("reimbursed_amount", 0) or 0)
        incurred_total += amt
        reimbursed_total += reimb
        if not r.get("reimbursed"):
            pending_count += 1
        cat = r.get("category") or "other"
        b = by_category.setdefault(cat, {"category": cat, "count": 0, "amount": 0.0, "reimbursed": 0.0})
        b["count"] += 1
        b["amount"] += amt
        b["reimbursed"] += reimb
    by_category_list = sorted(
        ({**b, "amount": round(b["amount"], 2), "reimbursed": round(b["reimbursed"], 2)}
         for b in by_category.values()),
        key=lambda x: x["amount"], reverse=True,
    )
    return {
        "incurred_total": round(incurred_total, 2),
        "reimbursed_total": round(reimbursed_total, 2),
        "net_cost": round(incurred_total - reimbursed_total, 2),
        "pending_count": pending_count,
        "by_category": by_category_list,
    }


@router.get("/inspections/{iid}")
async def get_inspection(iid: str, _: dict = Depends(get_current_user)):
    row = await db.inspections.find_one({"id": iid}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return row


@router.put("/inspections/{iid}")
async def update_inspection(
    iid: str,
    payload: InspectionIn,
    user: dict = Depends(require_not_cashier),
):
    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive")
    contract = await _load_contract_meta(payload.contract_id)
    update = {
        "contract_id": payload.contract_id,
        "contract_number": contract.get("contract_number", ""),
        "client_id": contract.get("client_id"),
        "item_type": contract.get("item_type"),
        "item_id": contract.get("item_id"),
        "category": payload.category,
        "description": payload.description,
        "amount": round(float(payload.amount), 2),
        "incurred_date": payload.incurred_date or date.today().isoformat(),
        "notes": payload.notes,
    }
    res = await db.inspections.update_one({"id": iid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inspection not found")
    await write_audit(user, "update", "inspection", iid, {"amount": update["amount"]})
    return await db.inspections.find_one({"id": iid}, {"_id": 0})


@router.post("/inspections/{iid}/reimburse")
async def reimburse_inspection(
    iid: str,
    payload: InspectionReimburseIn,
    user: dict = Depends(require_not_cashier),
):
    row = await db.inspections.find_one({"id": iid}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if payload.reimbursed_amount <= 0:
        raise HTTPException(status_code=422, detail="Reimbursed amount must be positive")
    update = {
        "reimbursed": True,
        "reimbursed_amount": round(float(payload.reimbursed_amount), 2),
        "reimbursed_date": payload.reimbursed_date or date.today().isoformat(),
    }
    await db.inspections.update_one({"id": iid}, {"$set": update})
    await write_audit(
        user, "reimburse", "inspection", iid,
        {"reimbursed_amount": update["reimbursed_amount"]},
    )
    rt_notify("inspection.reimbursed", {"id": iid, "amount": update["reimbursed_amount"]})
    return await db.inspections.find_one({"id": iid}, {"_id": 0})


@router.delete("/inspections/{iid}")
async def delete_inspection(iid: str, _: dict = Depends(require_admin)):
    res = await db.inspections.delete_one({"id": iid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return {"ok": True}
