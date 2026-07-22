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
    brand: str
    model: str
    description: str = ""
    plate: str = ""
    machine_number: str = ""  # engine/motor number
    chassis: str = ""         # VIN / frame number
    fuel_percent: int = 0
    color: str = ""
    manufacture_year: Optional[int] = None
    engine_cc: Optional[int] = None  # engine capacity in CC
    transmission: str = ""  # "manual" | "automatic" (free-text; UI limits it)
    market_value: float = 0.0
    location: str = ""  # warehouse / shop / off-site
    photo_url: str = ""
    thumbnail_url: str = ""
    document_url: str = ""


class MotorcycleIn(BaseModel):
    name: str = ""
    brand: str
    model: str
    description: str = ""
    plate: str = ""
    machine_number: str = ""
    chassis: str = ""
    fuel_percent: int = 0
    color: str = ""
    manufacture_year: Optional[int] = None
    engine_cc: Optional[int] = None
    transmission: str = ""
    market_value: float = 0.0
    location: str = ""
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
    color: str = ""
    operating_hours: Optional[int] = None
    manufacture_year: Optional[int] = None
    market_value: float = 0.0
    location: str = ""
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
