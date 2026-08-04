"""Warehouse receipt (iter 66).

After the office finalises a pawn contract for a physical asset (car,
motorcycle, pezadu), the item is transported to the warehouse. Warehouse
staff must **acknowledge receipt** — recording who received it, condition
notes, current fuel level, current mileage, and an optional photo. The
receipt is a one-time acknowledgement per contract.

Contracts of item_type `electronic` do not require a warehouse receipt
(handled by the office).

Endpoints:
  GET  /api/warehouse/pending
       Contracts that need warehouse acknowledgement (physical assets,
       active status, not yet received). Warehouse-staff view.
  POST /api/warehouse/receipts/{cid}
       Record acknowledgement.
  GET  /api/warehouse/receipts
       List completed receipts (audit-friendly).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import (
    db,
    utcnow_iso,
    get_current_user,
    require_module,
    write_audit,
)

router = APIRouter(tags=["warehouse"])

PHYSICAL_KINDS = ("car", "motorcycle", "pezadu")


class WarehouseReceiptIn(BaseModel):
    condition: str = ""      # "good" | "damaged" | free text
    fuel_percent: Optional[int] = None
    mileage_km: Optional[int] = None
    notes: str = ""
    photo_url: str = ""
    thumbnail_url: str = ""


@router.get("/warehouse/pending")
async def warehouse_pending(_: dict = Depends(require_module("warehouse"))):
    """Physical-asset contracts still awaiting warehouse receipt."""
    contracts = await db.contracts.find(
        {
            "item_type": {"$in": list(PHYSICAL_KINDS)},
            "status": {"$in": ["active", "grace_period"]},
            "$or": [
                {"warehouse_received": {"$exists": False}},
                {"warehouse_received": False},
            ],
        },
        {"_id": 0},
    ).sort("contract_date", -1).to_list(1000)
    # Enrich with client + item name
    clients = await db.clients.find({}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1}).to_list(5000)
    cmap = {c["id"]: c for c in clients}
    from deps import COLLECTION_MAP  # local import to avoid circulars
    out = []
    for c in contracts:
        item = None
        if c.get("item_id") and c.get("item_type") in COLLECTION_MAP:
            item = await db[COLLECTION_MAP[c["item_type"]]].find_one(
                {"id": c["item_id"]},
                {"_id": 0, "name": 1, "brand": 1, "model": 1, "plate": 1,
                 "fuel_percent": 1, "mileage_km": 1, "photo_url": 1},
            )
        cli = cmap.get(c.get("client_id"), {})
        out.append({
            "id": c["id"],
            "contract_number": c.get("contract_number"),
            "item_type": c.get("item_type"),
            "contract_date": c.get("contract_date"),
            "due_date": c.get("due_date"),
            "status": c.get("status"),
            "client_name": cli.get("full_name"),
            "client_phone": cli.get("phone"),
            "item": item or {},
        })
    return out


@router.post("/warehouse/receipts/{cid}")
async def confirm_warehouse_receipt(
    cid: str,
    payload: WarehouseReceiptIn,
    user: dict = Depends(require_module("warehouse")),
):
    """Warehouse staff confirms physical receipt of the pawned item."""
    c = await db.contracts.find_one({"id": cid}, {"_id": 0, "item_type": 1, "status": 1, "warehouse_received": 1})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if c.get("item_type") not in PHYSICAL_KINDS:
        raise HTTPException(status_code=400, detail="Only physical assets require warehouse receipt")
    if c.get("warehouse_received"):
        raise HTTPException(status_code=409, detail="Already acknowledged")
    now = datetime.now(timezone.utc).isoformat()
    update = {
        "warehouse_received": True,
        "warehouse_received_at": now,
        "warehouse_received_by": user.get("id"),
        "warehouse_received_by_name": user.get("name"),
        "warehouse_receipt_condition": payload.condition,
        "warehouse_receipt_fuel_percent": payload.fuel_percent,
        "warehouse_receipt_mileage_km": payload.mileage_km,
        "warehouse_receipt_notes": payload.notes,
        "warehouse_receipt_photo_url": payload.photo_url,
        "warehouse_receipt_thumbnail_url": payload.thumbnail_url,
    }
    await db.contracts.update_one({"id": cid}, {"$set": update})
    await write_audit(user, "warehouse_receive", "contract", cid, {
        "condition": payload.condition,
        "fuel_percent": payload.fuel_percent,
        "mileage_km": payload.mileage_km,
    })
    return await db.contracts.find_one({"id": cid}, {"_id": 0})


@router.get("/warehouse/receipts")
async def list_warehouse_receipts(_: dict = Depends(require_module("warehouse"))):
    """Completed warehouse receipts, newest first."""
    rows = await db.contracts.find(
        {"warehouse_received": True},
        {"_id": 0, "id": 1, "contract_number": 1, "item_type": 1,
         "warehouse_received_at": 1, "warehouse_received_by_name": 1,
         "warehouse_receipt_condition": 1, "warehouse_receipt_fuel_percent": 1,
         "warehouse_receipt_mileage_km": 1, "warehouse_receipt_notes": 1,
         "warehouse_receipt_photo_url": 1, "warehouse_receipt_thumbnail_url": 1,
         "client_id": 1},
    ).sort("warehouse_received_at", -1).to_list(2000)
    clients = await db.clients.find({}, {"_id": 0, "id": 1, "full_name": 1}).to_list(5000)
    cmap = {c["id"]: c for c in clients}
    for r in rows:
        r["client_name"] = cmap.get(r.get("client_id"), {}).get("full_name")
    return rows
