"""Public endpoints — auction items, warehouse (password-gated), contact form.

Extracted from server.py during Phase 2 refactor. These endpoints are
unauthenticated (no cookie required) except for /contact-messages which is
admin-only.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr

from deps import db, new_id, utcnow_iso, require_admin, COLLECTION_MAP
from services import _fetch_item, get_settings_doc

router = APIRouter()

@router.get("/public/auction-items")
async def public_auction_items(unlock_token: Optional[str] = Query(None)):
    """Public auction listing — gated by the same visitor password as the Warehouse.
    A token is required ONLY if a password has been configured by the admin."""
    s = await get_settings_doc()
    if s.get("warehouse_password_hash"):
        if not unlock_token or not _warehouse_token_valid(unlock_token):
            raise HTTPException(status_code=401, detail="Auction listing is locked")
    items = await db.auctions.find({"status": "listed"}, {"_id": 0}).sort("created_at", -1).to_list(500)
    out = []
    for a in items:
        item = await _fetch_item(a["item_type"], a["item_id"]) or {}
        out.append({
            "id": a["id"],
            "item_type": a["item_type"],
            "starting_price": a.get("starting_price", 0),
            "brand": item.get("brand", ""),
            "model": item.get("model", ""),
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "photo_url": item.get("photo_url", ""),
            "manufacture_year": item.get("manufacture_year"),
            "category": item.get("category"),
        })
    return out


@router.get("/public/auction-status")
async def public_auction_status():
    """Same lock state as the warehouse — public pages share one visitor password."""
    s = await get_settings_doc()
    return {"locked": bool(s.get("warehouse_password_hash"))}


@router.get("/public/warehouse")
async def public_warehouse(unlock_token: str = Query(...)):
    """Items currently held — gated by warehouse password.

    Frontend exchanges the user-entered password for a short-lived token via
    /api/public/warehouse-unlock; that token must be passed here.
    """
    if not _warehouse_token_valid(unlock_token):
        raise HTTPException(status_code=401, detail="Warehouse is locked")
    out = []
    for kind, coll in COLLECTION_MAP.items():
        items = await db[coll].find(
            {"status": {"$in": ["pawned", "in_stock"]}}, {"_id": 0}
        ).sort("created_at", -1).limit(30).to_list(30)
        for it in items:
            out.append({
                "id": it["id"],
                "kind": kind,
                "brand": it.get("brand", ""),
                "model": it.get("model", ""),
                "description": it.get("description", ""),
                "photo_url": it.get("photo_url", ""),
            })
    return out


class WarehouseUnlockIn(BaseModel):
    password: str


@router.post("/public/warehouse-unlock")
async def public_warehouse_unlock(payload: WarehouseUnlockIn):
    s = await get_settings_doc()
    hashed = s.get("warehouse_password_hash", "")
    if not hashed:
        # Not configured → leave open for backwards compat; admins should set one
        return {"ok": True, "token": _issue_warehouse_token(), "configured": False}
    from auth import verify_password
    if not verify_password(payload.password, hashed):
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"ok": True, "token": _issue_warehouse_token(), "configured": True}


@router.get("/public/warehouse-status")
async def public_warehouse_status():
    s = await get_settings_doc()
    return {"locked": bool(s.get("warehouse_password_hash"))}


def _issue_warehouse_token() -> str:
    """Sign a short-lived JWT (24h) for warehouse access."""
    import jwt
    from datetime import datetime, timezone, timedelta
    from auth import get_jwt_secret, JWT_ALGORITHM
    payload = {
        "scope": "warehouse",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _warehouse_token_valid(tok: str) -> bool:
    if not tok:
        return False
    try:
        from auth import decode_token
        data = decode_token(tok)
        return data.get("scope") == "warehouse"
    except Exception:  # noqa: BLE001
        return False



class ContactIn(BaseModel):
    name: str
    email: EmailStr
    phone: str = ""
    message: str


@router.post("/public/contact")
async def public_contact(payload: ContactIn):
    doc = payload.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.contact_messages.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "id": doc["id"]}


@router.get("/contact-messages")
async def contact_messages(_: dict = Depends(require_admin)):
    return await db.contact_messages.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)

