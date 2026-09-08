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

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deps import (
    db,
    COLLECTION_MAP,
    utcnow_iso,
    get_current_user,
    require_module,
    write_audit,
)
from pdf_utils import build_release_pass_pdf
from realtime import notify as rt_notify

router = APIRouter(tags=["warehouse"])

PHYSICAL_KINDS = ("car", "motorcycle", "pezadu")
RELEASE_ITEM_FIELDS = {"_id": 0, "name": 1, "brand": 1, "model": 1, "plate": 1, "serial": 1,
                       "fuel_percent": 1, "mileage_km": 1, "photo_url": 1, "status": 1, "location": 1}


class WarehouseReleaseIn(BaseModel):
    collector_name: str
    collector_id_number: str = ""
    collector_relation: str = "owner"   # owner | representative
    condition: str = "good"
    fuel_percent: Optional[int] = None
    mileage_km: Optional[int] = None
    notes: str = ""
    photo_url: str = ""
    thumbnail_url: str = ""


async def _client_map():
    clients = await db.clients.find({}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "id_number": 1}).to_list(5000)
    return {c["id"]: c for c in clients}


async def _release_row(c: dict, cmap: dict) -> dict:
    item = None
    if c.get("item_id") and c.get("item_type") in COLLECTION_MAP:
        item = await db[COLLECTION_MAP[c["item_type"]]].find_one({"id": c["item_id"]}, RELEASE_ITEM_FIELDS)
    cli = cmap.get(c.get("client_id"), {})
    return {
        "id": c["id"],
        "contract_number": c.get("contract_number"),
        "item_type": c.get("item_type"),
        "group": "warehouse" if c.get("item_type") in PHYSICAL_KINDS else "office",
        "contract_date": c.get("contract_date"),
        "redeemed_at": c.get("redeemed_at"),
        "status": c.get("status"),
        "client_id": c.get("client_id"),
        "client_name": cli.get("full_name"),
        "client_phone": cli.get("phone"),
        "client_id_number": cli.get("id_number"),
        "item": item or {},
        "item_released": bool(c.get("item_released")),
        "item_released_at": c.get("item_released_at"),
        "released_by_name": c.get("released_by_name"),
        "release_collector_name": c.get("release_collector_name"),
        "release_collector_id_number": c.get("release_collector_id_number"),
        "release_collector_relation": c.get("release_collector_relation"),
        "release_condition": c.get("release_condition"),
        "release_fuel_percent": c.get("release_fuel_percent"),
        "release_mileage_km": c.get("release_mileage_km"),
        "release_notes": c.get("release_notes"),
        "release_photo_url": c.get("release_photo_url"),
    }


@router.get("/warehouse/releases/pending")
async def releases_pending(_: dict = Depends(require_module("warehouse"))):
    """Fully-paid contracts whose item is still physically held (awaiting hand-over)."""
    contracts = await db.contracts.find(
        {"status": "redeemed", "$or": [{"item_released": {"$exists": False}}, {"item_released": False}]},
        {"_id": 0},
    ).sort("redeemed_at", -1).to_list(2000)
    cmap = await _client_map()
    rows = [await _release_row(c, cmap) for c in contracts]
    now = datetime.now(timezone.utc)
    for r in rows:
        r["days_waiting"] = _days_since(r.get("redeemed_at"), now)
        r["last_nudge_at"] = next((c.get("pickup_nudge_at") for c in contracts if c["id"] == r["id"]), None)
    # Nothing to hand over if the item record no longer exists (legacy/orphan contracts).
    return [r for r in rows if r["item"]]


def _days_since(iso: Optional[str], now: datetime) -> Optional[int]:
    if not iso:
        return None
    try:
        return max(0, (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days)
    except ValueError:
        return None


@router.get("/warehouse/releases/overdue")
async def releases_overdue(days: int = 7, _: dict = Depends(require_module("warehouse"))):
    """Paid-off items not collected for `days`+ days (default 7)."""
    rows = await releases_pending(_)
    return [r for r in rows if (r.get("days_waiting") or 0) >= max(1, days)]


@router.post("/warehouse/releases/{cid}/nudge")
async def release_nudge(cid: str, user: dict = Depends(require_module("warehouse"))):
    """Send the client a WhatsApp reminder that their item is still waiting for collection."""
    from routes.payments import _send_pickup_ready_whatsapp  # noqa: PLC0415
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if c.get("status") != "redeemed" or c.get("item_released"):
        raise HTTPException(status_code=400, detail="Item is not awaiting collection")
    result = await _send_pickup_ready_whatsapp(c, user, force=True, template="pickup_nudge")
    if result.get("status") in ("skipped", "failed"):
        raise HTTPException(status_code=400, detail=result.get("reason") or result.get("error") or "Send failed")
    now = utcnow_iso()
    await db.contracts.update_one({"id": cid}, {"$set": {"pickup_nudge_at": now}, "$inc": {"pickup_nudge_count": 1}})
    return {**result, "nudged_at": now}


@router.get("/warehouse/releases")
async def releases_history(_: dict = Depends(require_module("warehouse"))):
    """Completed hand-overs, newest first."""
    contracts = await db.contracts.find({"item_released": True}, {"_id": 0}) \
        .sort("item_released_at", -1).to_list(2000)
    cmap = await _client_map()
    return [await _release_row(c, cmap) for c in contracts]


@router.post("/warehouse/releases/{cid}")
async def release_item(cid: str, payload: WarehouseReleaseIn, user: dict = Depends(require_module("warehouse"))):
    """Hand the redeemed item back to the client and take it out of custody."""
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if c.get("status") != "redeemed":
        raise HTTPException(status_code=400, detail="Contract is not fully paid — item cannot be released")
    if c.get("item_released"):
        raise HTTPException(status_code=409, detail="Item already released")
    if not payload.collector_name.strip():
        raise HTTPException(status_code=422, detail="Collector name is required")
    now = utcnow_iso()
    update = {
        "item_released": True,
        "item_released_at": now,
        "released_by": user.get("id"),
        "released_by_name": user.get("name"),
        "release_collector_name": payload.collector_name.strip(),
        "release_collector_id_number": payload.collector_id_number.strip(),
        "release_collector_relation": payload.collector_relation,
        "release_condition": payload.condition,
        "release_fuel_percent": payload.fuel_percent,
        "release_mileage_km": payload.mileage_km,
        "release_notes": payload.notes,
        "release_photo_url": payload.photo_url,
        "release_thumbnail_url": payload.thumbnail_url,
    }
    await db.contracts.update_one({"id": cid}, {"$set": update})
    if c.get("item_type") in COLLECTION_MAP and c.get("item_id"):
        await db[COLLECTION_MAP[c["item_type"]]].update_one(
            {"id": c["item_id"]},
            {"$set": {"status": "released", "released_at": now}, "$unset": {"active_contract_id": ""}},
        )
    await write_audit(user, "warehouse_release", "contract", cid, {
        "contract_number": c.get("contract_number"),
        "collector_name": payload.collector_name,
        "collector_id_number": payload.collector_id_number,
        "condition": payload.condition,
    })
    rt_notify("item.released", {
        "contract_id": cid,
        "contract_number": c.get("contract_number"),
        "item_type": c.get("item_type"),
        "collector_name": payload.collector_name,
    })
    cmap = await _client_map()
    return await _release_row({**c, **update}, cmap)


@router.get("/warehouse/releases/{cid}/pdf")
async def release_pass_pdf(cid: str, _: dict = Depends(get_current_user)):
    """Gate pass / hand-over receipt PDF for a released item."""
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not c.get("item_released"):
        raise HTTPException(status_code=400, detail="Item has not been released yet")
    client_doc = await db.clients.find_one({"id": c.get("client_id")}, {"_id": 0}) or {}
    item = {}
    if c.get("item_type") in COLLECTION_MAP and c.get("item_id"):
        item = await db[COLLECTION_MAP[c["item_type"]]].find_one({"id": c["item_id"]}, {"_id": 0}) or {}
    pdf_bytes = build_release_pass_pdf(c, client_doc, item)
    fname = f'{c.get("contract_number", "contract")}-release.pdf'
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{fname}"'})


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
