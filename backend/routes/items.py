"""Items domain routes.

Extracted from server.py during the Phase-3 server split (iter 58). Owns the
car / motorcycle / electronic / pezadu item collections. Every endpoint keeps
its exact path, method, auth dependency, and response shape so this is a pure
refactor — no behavioural changes.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import (
    db,
    new_id,
    utcnow_iso,
    COLLECTION_MAP,
    require_admin,
    require_module,
    require_not_cashier,
    get_current_user,
    write_audit,
)
from services import ITEM_KINDS

router = APIRouter(tags=["items"])

PEZADU_CATEGORIES = {"forklift", "tractor", "loader", "heavy_duty_truck"}


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------
class CarIn(BaseModel):
    name: str = ""  # human-friendly label e.g. "Toyota Hilux 2020 Black"
    category: str = ""  # sedan / suv / pickup / truck / van / hatchback / mini_bus / other
    brand: str
    model: str
    description: str = ""
    plate: str = ""
    machine_number: str = ""  # engine/motor number
    chassis: str = ""         # VIN / frame number
    fuel_percent: int = 0
    fuel_type: str = ""       # "petrol" | "diesel" | ""
    mileage_km: Optional[int] = None  # odometer reading in km at pawn time
    color: str = ""
    manufacture_year: Optional[int] = None
    engine_cc: Optional[int] = None  # engine capacity in CC
    transmission: str = ""  # "manual" | "automatic" (free-text; UI limits it)
    market_value: float = 0.0
    location: str = ""  # warehouse / shop / off-site
    received_by: str = ""       # user_id of the staff who intook the item
    responsible_staff: str = ""  # user_id currently responsible for it
    photo_url: str = ""
    thumbnail_url: str = ""
    document_url: str = ""


class MotorcycleIn(BaseModel):
    name: str = ""
    category: str = ""  # scooter / cub / sport / adventure / dirt_bike / e_bike / other
    brand: str
    model: str
    description: str = ""
    plate: str = ""
    machine_number: str = ""
    chassis: str = ""
    fuel_percent: int = 0
    fuel_type: str = ""
    mileage_km: Optional[int] = None
    color: str = ""
    manufacture_year: Optional[int] = None
    engine_cc: Optional[int] = None
    transmission: str = ""
    market_value: float = 0.0
    location: str = ""
    received_by: str = ""
    responsible_staff: str = ""
    photo_url: str = ""
    thumbnail_url: str = ""
    document_url: str = ""


class ElectronicIn(BaseModel):
    category: str
    brand: str
    model: str
    description: str = ""
    serial: str = ""
    condition: str = ""
    manufacture_year: Optional[int] = None
    market_value: float = 0.0
    location: str = ""
    received_by: str = ""
    responsible_staff: str = ""
    photo_url: str = ""
    thumbnail_url: str = ""
    document_url: str = ""


class PezaduIn(BaseModel):
    name: str = ""  # human-friendly label
    category: str  # forklift / tractor / loader / heavy_duty_truck
    brand: str
    model: str
    description: str = ""
    plate: str = ""
    machine_number: str = ""  # engine/motor number
    chassis: str = ""
    serial: str = ""
    fuel_percent: int = 0
    fuel_type: str = ""
    mileage_km: Optional[int] = None
    color: str = ""
    operating_hours: Optional[int] = None
    manufacture_year: Optional[int] = None
    market_value: float = 0.0
    location: str = ""
    received_by: str = ""
    responsible_staff: str = ""
    photo_url: str = ""
    thumbnail_url: str = ""
    document_url: str = ""


def _item_model(kind: str):
    return {
        "car": CarIn,
        "motorcycle": MotorcycleIn,
        "electronic": ElectronicIn,
        "pezadu": PezaduIn,
    }[kind]


def _validate_kind(kind: str) -> None:
    if kind not in ITEM_KINDS:
        raise HTTPException(status_code=400, detail="Invalid item kind")


# ---------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------
@router.get("/items/{kind}")
async def list_items(kind: str, _: dict = Depends(require_module("items"))):
    _validate_kind(kind)
    coll = db[COLLECTION_MAP[kind]]
    items = await coll.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    # Coerce category='' on legacy rows so JSON consumers can always read the
    # field (iter74 backward-compat fix — legacy Mongo docs lacked the field
    # entirely so the response would omit the key).
    if kind in ("car", "motorcycle"):
        for r in items:
            r.setdefault("category", "")
    return items


@router.post("/items/{kind}")
async def create_item(kind: str, payload: dict, user: dict = Depends(require_not_cashier)):
    _validate_kind(kind)
    model = _item_model(kind)
    try:
        validated = model(**payload).model_dump()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    doc = {**validated, "id": new_id(), "kind": kind, "status": "in_stock",
           "created_at": utcnow_iso()}
    await db[COLLECTION_MAP[kind]].insert_one(doc)
    await write_audit(user, "create", f"item.{kind}", doc["id"],
                      {"brand": doc.get("brand"), "model": doc.get("model")})
    doc.pop("_id", None)
    return doc


@router.get("/items/{kind}/{iid}")
async def get_item(kind: str, iid: str, _: dict = Depends(get_current_user)):
    _validate_kind(kind)
    it = await db[COLLECTION_MAP[kind]].find_one({"id": iid}, {"_id": 0})
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    return it


@router.put("/items/{kind}/{iid}")
async def update_item(kind: str, iid: str, payload: dict, _: dict = Depends(get_current_user)):
    _validate_kind(kind)
    model = _item_model(kind)
    try:
        validated = model(**payload).model_dump()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    res = await db[COLLECTION_MAP[kind]].update_one({"id": iid}, {"$set": validated})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    it = await db[COLLECTION_MAP[kind]].find_one({"id": iid}, {"_id": 0})
    return it


@router.delete("/items/{kind}/{iid}")
async def delete_item(kind: str, iid: str, _: dict = Depends(require_admin)):
    _validate_kind(kind)
    res = await db[COLLECTION_MAP[kind]].delete_one({"id": iid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


# ---------------------------------------------------------------------
# Bulk photo attach — used by the Items page bulk uploader.
# Frontend uploads each file via /api/upload (which produces thumbnails)
# and then PATCHes just the photo_url + thumbnail_url onto each item.
# ---------------------------------------------------------------------
class PhotoPatchIn(BaseModel):
    photo_url: str
    thumbnail_url: str = ""


@router.patch("/items/{kind}/{iid}/photo")
async def patch_item_photo(
    kind: str,
    iid: str,
    payload: PhotoPatchIn,
    user: dict = Depends(require_not_cashier),
):
    _validate_kind(kind)
    update = {"photo_url": payload.photo_url, "thumbnail_url": payload.thumbnail_url}
    res = await db[COLLECTION_MAP[kind]].update_one({"id": iid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    await write_audit(user, "attach_photo", f"item.{kind}", iid, {"photo_url": payload.photo_url})
    it = await db[COLLECTION_MAP[kind]].find_one({"id": iid}, {"_id": 0})
    return it


# ---------------------------------------------------------------------
# Staff assignment (Phase E). Attach `received_by` and/or `responsible_staff`
# user IDs to an item so warehouse / office custody is traceable.
# ---------------------------------------------------------------------
class StaffPatchIn(BaseModel):
    received_by: Optional[str] = None       # None = unchanged
    responsible_staff: Optional[str] = None  # None = unchanged


@router.patch("/items/{kind}/{iid}/staff")
async def patch_item_staff(
    kind: str,
    iid: str,
    payload: StaffPatchIn,
    user: dict = Depends(require_not_cashier),
):
    _validate_kind(kind)
    update: dict = {}
    if payload.received_by is not None:
        update["received_by"] = payload.received_by
    if payload.responsible_staff is not None:
        update["responsible_staff"] = payload.responsible_staff
    if not update:
        raise HTTPException(status_code=422, detail="Nothing to update")
    res = await db[COLLECTION_MAP[kind]].update_one({"id": iid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    await write_audit(user, "assign_staff", f"item.{kind}", iid, update)
    it = await db[COLLECTION_MAP[kind]].find_one({"id": iid}, {"_id": 0})
    return it


@router.get("/staff/assignments")
async def staff_assignments(_: dict = Depends(get_current_user)):
    """Group active pawnable items by responsible staff, split by
    warehouse (vehicles + pezadu) and office (electronics)."""
    from motor.motor_asyncio import AsyncIOMotorDatabase  # noqa: F401  (typing only)

    users = await db.users.find(
        {}, {"_id": 0, "id": 1, "name": 1, "email": 1, "staff_type": 1, "role": 1}
    ).to_list(500)
    user_map = {u["id"]: u for u in users if u.get("id")}

    warehouse_kinds = ("car", "motorcycle", "pezadu")
    office_kinds = ("electronic",)
    buckets: dict[str, dict] = {}

    async def _collect(kind: str, group: str):
        coll = db[COLLECTION_MAP[kind]]
        async for it in coll.find({}, {"_id": 0}):
            uid = (it.get("responsible_staff") or "").strip()
            # Unassigned rows go into per-group buckets so warehouse and
            # office each show their own "Unassigned" pile.
            key = uid or f"__unassigned__{group}"
            bucket = buckets.setdefault(key, {
                "user_id": uid or None,
                "name": user_map.get(uid, {}).get("name") if uid else "Unassigned",
                "email": user_map.get(uid, {}).get("email") if uid else "",
                "staff_type": user_map.get(uid, {}).get("staff_type") if uid else "",
                "group": group,
                "items": [],
                "total_market_value": 0.0,
            })
            # Trim item payload — we only need identity + summary fields
            # the UI actually shows for the assignments card.
            row = {
                "id": it.get("id"),
                "kind": kind,
                "name": it.get("name") or f"{it.get('brand','')} {it.get('model','')}".strip(),
                "brand": it.get("brand"),
                "model": it.get("model"),
                "plate": it.get("plate"),
                "serial": it.get("serial"),
                "fuel_type": it.get("fuel_type"),
                "mileage_km": it.get("mileage_km"),
                "market_value": float(it.get("market_value", 0) or 0),
                "location": it.get("location"),
                "status": it.get("status"),
                "received_by": it.get("received_by"),
            }
            bucket["items"].append(row)
            bucket["total_market_value"] += row["market_value"]

    for k in warehouse_kinds:
        await _collect(k, "warehouse")
    for k in office_kinds:
        await _collect(k, "office")

    # Add any staff users who exist but currently have no items so the UI
    # can show them as "0 items" (useful for onboarding a new custodian).
    for u in users:
        st = u.get("staff_type") or ""
        if st in ("warehouse", "office") and u["id"] not in buckets:
            buckets[u["id"]] = {
                "user_id": u["id"],
                "name": u.get("name"),
                "email": u.get("email"),
                "staff_type": st,
                "group": st,
                "items": [],
                "total_market_value": 0.0,
            }

    def _key(b):
        # Unassigned sinks to the bottom; then sort by count desc, then name.
        is_unassigned = b["user_id"] is None
        return (is_unassigned, -len(b["items"]), (b.get("name") or "").lower())

    warehouse = sorted(
        (b for b in buckets.values() if b["group"] == "warehouse" or (b["staff_type"] == "warehouse" and b["group"] != "office")),
        key=_key,
    )
    office = sorted(
        (b for b in buckets.values() if b["group"] == "office" or b["staff_type"] == "office"),
        key=_key,
    )
    # De-dupe: an "Unassigned" bucket for each group is fine, but a warehouse
    # user shouldn't also appear under office (or vice versa). If a staff has
    # items in both groups, keep them in the group matching their staff_type.
    def _dedupe(rows, group):
        keep = []
        seen = set()
        for b in rows:
            if b["user_id"] and b["staff_type"] and b["staff_type"] != group:
                continue
            k = (b["user_id"], group)
            if k in seen:
                continue
            seen.add(k)
            keep.append({**b, "total_market_value": round(b["total_market_value"], 2)})
        return keep

    return {
        "warehouse": _dedupe(warehouse, "warehouse"),
        "office": _dedupe(office, "office"),
        "staff": [
            {"id": u["id"], "name": u.get("name"), "email": u.get("email"),
             "staff_type": u.get("staff_type", "")}
            for u in users if u.get("id")
        ],
    }
