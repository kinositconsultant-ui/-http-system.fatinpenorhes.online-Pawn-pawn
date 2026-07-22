"""Clients domain routes.

Extracted from server.py during the Phase-3 server split (iter 57). Owns:
  • Client CRUD (`/api/clients`, `/api/clients/{cid}`, …)
  • Client-scoped contract / payment history views
  • Member ID cards — issue / renew / revoke / PDF
  • Public verify endpoints backed by the QR-code token

Every endpoint keeps its exact path, method, auth dependency, and response
shape so this is a pure refactor — no behavioural changes.
"""
from __future__ import annotations

import os
import secrets as _secrets
from datetime import date, datetime, timezone, timedelta
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel

import storage as objstore
from deps import (
    db,
    new_id,
    utcnow_iso,
    require_admin,
    require_module,
    require_not_cashier,
    get_current_user,
    write_audit,
)
from services import _recompute_contract_status
from pdf_utils import build_member_card_pdf

router = APIRouter(tags=["clients"])


# ---------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------
class ClientIn(BaseModel):
    full_name: str
    id_type: Literal["BI", "Electoral", "Passport", "Drivers License"]
    id_number: str
    phone: str
    address: str = ""
    municipality: str = ""
    posto: str = ""
    suco: str = ""
    aldeia: str = ""
    photo_url: str = ""
    thumbnail_url: str = ""
    notes: str = ""


def _ensure_member_verify_token(doc: dict) -> None:
    """If client has a photo but no member_verify_token, auto-issue one so
    Clients.js list can render the thumbnail via the public photo endpoint
    (fallback path when thumbnail_url is not yet set)."""
    if doc.get("photo_url") and not doc.get("member_verify_token"):
        doc["member_verify_token"] = _secrets.token_urlsafe(18)


# ---------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------
@router.get("/clients")
async def list_clients(_: dict = Depends(require_module("clients"))):
    items = await db.clients.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    # Enrich each client with a lightweight risk profile so the frontend can
    # render a green/amber/red pill without a second round-trip.
    contracts = await db.contracts.find(
        {"status": {"$in": ["active", "overdue", "grace_period", "auction_ready"]}},
        {"_id": 0, "client_id": 1, "status": 1, "principal_remaining": 1,
         "loan_amount": 1, "days_overdue": 1},
    ).to_list(5000)
    total_book = sum(float(c.get("principal_remaining", c.get("loan_amount", 0)) or 0) for c in contracts)
    by_client: dict[str, dict] = {}
    for c in contracts:
        cid = c.get("client_id")
        if not cid:
            continue
        s = by_client.setdefault(cid, {
            "principal": 0.0, "overdue_days": 0, "auction_ready": 0, "active": 0,
        })
        s["principal"] += float(c.get("principal_remaining", c.get("loan_amount", 0)) or 0)
        s["overdue_days"] = max(s["overdue_days"], int(c.get("days_overdue", 0) or 0))
        if c.get("status") == "auction_ready":
            s["auction_ready"] += 1
        elif c.get("status") == "active":
            s["active"] += 1
    for it in items:
        s = by_client.get(it["id"])
        if not s:
            it["risk_level"] = "none"
            it["risk_concentration_pct"] = 0.0
            continue
        pct = (s["principal"] / total_book * 100.0) if total_book else 0.0
        # 3-tier scoring: any auction_ready OR >15% concentration → red;
        # >5% or has overdue → amber; otherwise green.
        if s["auction_ready"] > 0 or pct > 15.0:
            level = "red"
        elif pct > 5.0 or s["overdue_days"] > 0:
            level = "amber"
        else:
            level = "green"
        it["risk_level"] = level
        it["risk_concentration_pct"] = round(pct, 1)
        it["risk_overdue_days"] = s["overdue_days"]
        it["risk_auction_ready"] = s["auction_ready"]
    return items


@router.post("/clients")
async def create_client(payload: ClientIn, user: dict = Depends(require_not_cashier)):
    doc = payload.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    _ensure_member_verify_token(doc)
    await db.clients.insert_one(doc)
    await write_audit(user, "create", "client", doc["id"], {"full_name": doc["full_name"]})
    doc.pop("_id", None)
    return doc


@router.get("/clients/{cid}")
async def get_client(cid: str, _: dict = Depends(get_current_user)):
    c = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return c


@router.get("/clients/{cid}/contracts")
async def client_contracts(cid: str, _: dict = Depends(get_current_user)):
    rows = await db.contracts.find({"client_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(500)
    out = []
    for r in rows:
        out.append(await _recompute_contract_status(r))
    return out


@router.get("/clients/{cid}/payments")
async def client_payment_history(cid: str, _: dict = Depends(get_current_user)):
    """Return every payment for every contract owned by this client (full history)."""
    contracts = await db.contracts.find({"client_id": cid}, {"_id": 0}).to_list(500)
    if not contracts:
        return []
    contract_ids = [c["id"] for c in contracts]
    by_id = {c["id"]: c for c in contracts}
    payments = await db.payments.find(
        {"contract_id": {"$in": contract_ids}}, {"_id": 0}
    ).sort("date", -1).to_list(2000)
    for p in payments:
        c = by_id.get(p["contract_id"], {})
        p["contract_number"] = c.get("contract_number")
        p["item_type"] = c.get("item_type")
    return payments


@router.put("/clients/{cid}")
async def update_client(cid: str, payload: ClientIn, _: dict = Depends(get_current_user)):
    existing = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Client not found")
    update = payload.model_dump()
    # Auto-issue member_verify_token if photo is uploaded and no token yet
    if update.get("photo_url") and not existing.get("member_verify_token"):
        update["member_verify_token"] = _secrets.token_urlsafe(18)
    res = await db.clients.update_one({"id": cid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    c = await db.clients.find_one({"id": cid}, {"_id": 0})
    return c


@router.delete("/clients/{cid}")
async def delete_client(cid: str, _: dict = Depends(require_admin)):
    res = await db.clients.delete_one({"id": cid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"ok": True}


# =====================================================================
# Member ID Cards — issue / renew / revoke / verify / PDF
# =====================================================================
async def _generate_member_no() -> str:
    """Yearly sequence: FP-<YEAR>-<0000>."""
    year = datetime.now(timezone.utc).year
    prefix = f"FP-{year}-"
    last = await db.clients.find(
        {"member_no": {"$regex": f"^{prefix}"}}
    ).sort("member_no", -1).limit(1).to_list(1)
    if last:
        try:
            seq = int(last[0]["member_no"].split("-")[-1]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def _public_verify_url(token: str) -> str:
    """Public URL a QR code should point to."""
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        base = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    return f"{base}/verify/{token}"


def _card_status(c: dict) -> str:
    """Return live status: revoked → revoked; else expired if past expiry; else the stored status."""
    if not c.get("member_no"):
        return "none"
    if c.get("member_status") == "revoked":
        return "revoked"
    exp = c.get("member_expires_at") or ""
    if exp:
        try:
            if date.fromisoformat(exp[:10]) < date.today():
                return "expired"
        except Exception:
            pass
    return c.get("member_status") or "active"


@router.post("/clients/{cid}/issue-card")
async def issue_member_card(cid: str, user: dict = Depends(require_not_cashier)):
    client = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    member_no = client.get("member_no") or await _generate_member_no()
    today = date.today()
    expires = today + timedelta(days=365)
    token = client.get("member_verify_token") or _secrets.token_urlsafe(18)
    updates = {
        "member_no": member_no,
        "member_status": "active",
        "member_issued_at": today.isoformat(),
        "member_expires_at": expires.isoformat(),
        "member_verify_token": token,
    }
    await db.clients.update_one({"id": cid}, {"$set": updates})
    await write_audit(user, "issue_card", "client", cid, {"member_no": member_no})
    client.update(updates)
    return {"ok": True, **updates}


@router.post("/clients/{cid}/renew-card")
async def renew_member_card(cid: str, user: dict = Depends(require_not_cashier)):
    client = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.get("member_no"):
        raise HTTPException(status_code=400, detail="No card issued yet — issue first")
    today = date.today()
    expires = today + timedelta(days=365)
    updates = {
        "member_status": "active",
        "member_issued_at": today.isoformat(),
        "member_expires_at": expires.isoformat(),
    }
    await db.clients.update_one({"id": cid}, {"$set": updates})
    await write_audit(user, "renew_card", "client", cid, {"member_no": client.get("member_no")})
    return {"ok": True, **updates}


@router.post("/clients/{cid}/revoke-card")
async def revoke_member_card(cid: str, user: dict = Depends(require_admin)):
    client = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.get("member_no"):
        raise HTTPException(status_code=400, detail="No card issued")
    await db.clients.update_one({"id": cid}, {"$set": {"member_status": "revoked"}})
    await write_audit(user, "revoke_card", "client", cid, {"member_no": client.get("member_no")})
    return {"ok": True, "member_status": "revoked"}


@router.get("/clients/{cid}/card-pdf")
async def member_card_pdf(cid: str, _: dict = Depends(require_module("clients"))):
    client = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.get("member_no") or not client.get("member_verify_token"):
        raise HTTPException(status_code=400, detail="No card issued yet — issue first")
    client["member_status"] = _card_status(client)
    photo_bytes: bytes | None = None
    photo = (client.get("photo_url") or "").strip()
    if photo and not photo.lower().startswith(("http://", "https://")):
        storage_key = photo
        for prefix in ("/api/files/", "/files/", "/api/"):
            if storage_key.startswith(prefix):
                storage_key = storage_key[len(prefix):]
                break
        storage_key = storage_key.lstrip("/")
        try:
            photo_bytes, _ct = objstore.get_object(storage_key)
        except Exception:
            photo_bytes = None
    verify_url = _public_verify_url(client["member_verify_token"])
    pdf = build_member_card_pdf(client, verify_url, photo_bytes=photo_bytes)
    safe_no = (client["member_no"] or "card").replace("/", "-")
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="member-card-{safe_no}.pdf"'},
    )


@router.get("/public/verify/{token}/photo")
async def public_verify_member_photo(token: str):
    """Public — streams the client's photo for the given verify token."""
    if not token or len(token) < 8:
        raise HTTPException(status_code=404, detail="Not found")
    client = await db.clients.find_one({"member_verify_token": token}, {"_id": 0})
    if not client or not client.get("photo_url"):
        raise HTTPException(status_code=404, detail="No photo")
    photo = str(client["photo_url"]).strip()
    if photo.lower().startswith(("http://", "https://")):
        return RedirectResponse(url=photo, status_code=307)
    storage_key = photo
    for prefix in ("/api/files/", "/files/", "/api/"):
        if storage_key.startswith(prefix):
            storage_key = storage_key[len(prefix):]
            break
    storage_key = storage_key.lstrip("/")
    try:
        data, content_type = objstore.get_object(storage_key)
    except Exception:
        raise HTTPException(status_code=404, detail="Photo not accessible")
    return Response(content=data, media_type=content_type or "image/jpeg")


@router.get("/public/verify/{token}")
async def public_verify_member(token: str):
    """Public — anyone with the token (from QR scan) can verify the card."""
    if not token or len(token) < 8:
        raise HTTPException(status_code=404, detail="Not found")
    client = await db.clients.find_one({"member_verify_token": token}, {"_id": 0})
    if not client:
        return {"valid": False, "status": "not_found"}
    status = _card_status(client)
    photo_public = ""
    if client.get("photo_url"):
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        photo_public = f"{base}/api/public/verify/{token}/photo" if base else f"/api/public/verify/{token}/photo"
    return {
        "valid": status == "active",
        "status": status,
        "member_no": client.get("member_no"),
        "full_name": client.get("full_name"),
        "photo_url": photo_public,
        "issued_at": client.get("member_issued_at"),
        "expires_at": client.get("member_expires_at"),
        "company": "FATIN PENHORES UNIPESSOAL, LDA",
    }
