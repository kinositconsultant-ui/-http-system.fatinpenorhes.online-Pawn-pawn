"""Report Saved Views router — per-user filter + sort + tab presets.

Each authenticated user can save any number of named views. A view stores:
- tab       — which report tab it applies to (active-contracts, payments, …)
- filters   — arbitrary JSON dict (month / year / category / sub_category / …)
- sort      — { key, dir } or null
- name      — unique per user (case-insensitive)

Endpoints (auth required, scoped to the current user only):
  GET    /api/report-views                → list all views for current user
  POST   /api/report-views                → create/update by name (upsert)
  DELETE /api/report-views/{view_id}      → remove one view
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from deps import db, new_id, utcnow_iso, get_current_user

router = APIRouter()


class SortIn(BaseModel):
    key: str
    dir: str = Field(pattern="^(asc|desc)$")


class ReportViewIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=60)
    tab: str = Field(min_length=1, max_length=40)
    filters: dict = Field(default_factory=dict)
    sort: Optional[SortIn] = None
    pinned: bool = False
    alert_threshold: Optional[int] = Field(default=None, ge=0, le=100000)


class ThresholdIn(BaseModel):
    alert_threshold: Optional[int] = Field(default=None, ge=0, le=100000)


@router.get("/report-views")
async def list_views(user: dict = Depends(get_current_user)):
    rows = await db.report_views.find(
        {"user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    return rows


@router.post("/report-views")
async def upsert_view(payload: ReportViewIn, user: dict = Depends(get_current_user)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    existing = await db.report_views.find_one(
        {"user_id": user["id"], "name_lc": name.lower()}, {"_id": 0},
    )
    doc = {
        "user_id": user["id"],
        "name": name,
        "name_lc": name.lower(),
        "tab": payload.tab,
        "filters": payload.filters or {},
        "sort": payload.sort.model_dump() if payload.sort else None,
        "pinned": bool(payload.pinned),
        "alert_threshold": payload.alert_threshold,
        "updated_at": utcnow_iso(),
    }
    if existing:
        # Preserve existing pinned state unless explicitly set to True on this call.
        if not payload.pinned:
            doc["pinned"] = bool(existing.get("pinned", False))
        # Preserve threshold unless caller explicitly provided one
        if payload.alert_threshold is None and existing.get("alert_threshold") is not None:
            doc["alert_threshold"] = existing["alert_threshold"]
        await db.report_views.update_one({"id": existing["id"]}, {"$set": doc})
        doc["id"] = existing["id"]
        doc["created_at"] = existing.get("created_at", doc["updated_at"])
    else:
        doc["id"] = new_id()
        doc["created_at"] = doc["updated_at"]
        await db.report_views.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/report-views/{view_id}/pin")
async def toggle_pin(view_id: str, user: dict = Depends(get_current_user)):
    """Toggle the pinned flag for a saved view (owner only)."""
    v = await db.report_views.find_one(
        {"id": view_id, "user_id": user["id"]}, {"_id": 0},
    )
    if not v:
        raise HTTPException(status_code=404, detail="View not found")
    new_pinned = not bool(v.get("pinned", False))
    await db.report_views.update_one(
        {"id": view_id, "user_id": user["id"]},
        {"$set": {"pinned": new_pinned, "updated_at": utcnow_iso()}},
    )
    v["pinned"] = new_pinned
    return v


@router.patch("/report-views/{view_id}/threshold")
async def set_threshold(view_id: str, payload: ThresholdIn, user: dict = Depends(get_current_user)):
    """Set (or clear via null) the alert row-count threshold for a pinned view."""
    v = await db.report_views.find_one(
        {"id": view_id, "user_id": user["id"]}, {"_id": 0},
    )
    if not v:
        raise HTTPException(status_code=404, detail="View not found")
    await db.report_views.update_one(
        {"id": view_id, "user_id": user["id"]},
        {"$set": {"alert_threshold": payload.alert_threshold, "updated_at": utcnow_iso()}},
    )
    v["alert_threshold"] = payload.alert_threshold
    return v


@router.delete("/report-views/{view_id}")
async def delete_view(view_id: str, user: dict = Depends(get_current_user)):
    res = await db.report_views.delete_one({"id": view_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="View not found")
    return {"ok": True}
