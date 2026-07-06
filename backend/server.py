"""Fatin Penhores Pawn System — FastAPI backend."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from datetime import datetime, timezone, date, timedelta
from dateutil.relativedelta import relativedelta
from math import ceil
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, UploadFile, File, Form, Query, Header
from fastapi.responses import StreamingResponse, RedirectResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from io import BytesIO

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    set_auth_cookies,
    clear_auth_cookies,
    decode_token,
)
from pdf_utils import (
    build_contract_pdf,
    build_loan_terms_card_pdf,
    build_receipt_pdf,
    build_report_pdf,
    build_invoice_pdf,
    build_invoices_list_pdf,
    build_capital_sources_pdf,
    build_expenses_pdf,
    build_finance_summary_pdf,
    build_member_card_pdf,
    DEFAULT_TNC_EN,
    DEFAULT_TNC_TET,
)
import storage as objstore
import whatsapp as wapp

# Shared dependencies + helpers (extracted iter17 refactor)
from deps import (
    db,
    logger,
    utcnow_iso,
    new_id,
    ALL_MODULES,
    ROLE_DEFAULT_MODULES,
    COLLECTION_MAP,
    get_current_user,
    require_admin,
    require_module,
    require_roles,
    require_not_cashier,
    write_audit,
    months_billed as _months_billed,
)
# Cross-domain services (extracted Phase 2 refactor)
from services import (
    ITEM_KINDS,
    DEFAULT_SETTINGS,
    _today_iso,
    _fetch_item,
    get_settings_doc,
    _decrypted_settings,
    _recompute_contract_status,
    _wa_template_name,
    _wa_lang_code,
    _send_reminder_for_contract,
)

app = FastAPI(title="Fatin Penhores Pawn System")
api = APIRouter(prefix="/api")

# Configure root logger (deps.logger uses this)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# =====================================================================
# Auth models
# =====================================================================
class LoginIn(BaseModel):
    email: EmailStr
    password: str
    remember: bool = False  # "Remember me" → 30-day refresh cookie


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    allowed_modules: List[str] = []


@api.post("/auth/login")
async def auth_login(payload: LoginIn, response: Response):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"], remember=payload.remember)
    set_auth_cookies(response, access, refresh, remember=payload.remember)
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "allowed_modules": user.get("allowed_modules", []),
    }


@api.post("/auth/logout")
async def auth_logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me", response_model=UserOut)
async def auth_me(user: dict = Depends(get_current_user)):
    return UserOut(**user)


@api.post("/auth/refresh")
async def auth_refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    remember = bool(payload.get("remember", False))
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"], remember=remember)
    set_auth_cookies(response, access, refresh, remember=remember)
    return {"ok": True}


# =====================================================================
# Users (admin manages staff)
# =====================================================================
class UserCreateIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["admin", "staff", "cashier"] = "staff"
    allowed_modules: Optional[List[str]] = None  # if None, falls back to ROLE_DEFAULT_MODULES[role]


class UserUpdateIn(BaseModel):
    name: Optional[str] = None
    role: Optional[Literal["admin", "staff", "cashier"]] = None
    allowed_modules: Optional[List[str]] = None
    password: Optional[str] = None


@api.get("/users")
async def list_users(_: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users


@api.post("/users")
async def create_user(payload: UserCreateIn, _: dict = Depends(require_admin)):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already exists")
    # Resolve modules: explicit > role default. Validate against ALL_MODULES.
    modules = payload.allowed_modules if payload.allowed_modules is not None else ROLE_DEFAULT_MODULES.get(payload.role, [])
    modules = [m for m in modules if m in ALL_MODULES]
    if payload.role == "admin":
        modules = list(ALL_MODULES)  # admin always full
    doc = {
        "id": new_id(),
        "email": email,
        "name": payload.name,
        "role": payload.role,
        "allowed_modules": modules,
        "password_hash": hash_password(payload.password),
        "created_at": utcnow_iso(),
    }
    await db.users.insert_one(doc)
    doc.pop("password_hash")
    doc.pop("_id", None)
    return doc


@api.patch("/users/{user_id}")
async def update_user(user_id: str, payload: UserUpdateIn, admin: dict = Depends(require_admin)):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updates: dict = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.role is not None:
        updates["role"] = payload.role
    if payload.allowed_modules is not None:
        modules = [m for m in payload.allowed_modules if m in ALL_MODULES]
        updates["allowed_modules"] = modules
    # If role is being set to admin (now), force full module access.
    final_role = payload.role if payload.role is not None else user.get("role")
    if final_role == "admin":
        updates["allowed_modules"] = list(ALL_MODULES)
    if payload.password:
        updates["password_hash"] = hash_password(payload.password)
    if updates:
        await db.users.update_one({"id": user_id}, {"$set": updates})
    out = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return out


@api.get("/users/modules")
async def list_user_modules(_: dict = Depends(require_admin)):
    """Catalog endpoint for the frontend user form — list of valid modules + per-role defaults."""
    return {"modules": ALL_MODULES, "role_defaults": ROLE_DEFAULT_MODULES}


@api.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    res = await db.users.delete_one({"id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


# =====================================================================
# Clients
# =====================================================================
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
    notes: str = ""


@api.get("/clients")
async def list_clients(_: dict = Depends(require_module("clients"))):
    items = await db.clients.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@api.post("/clients")
async def create_client(payload: ClientIn, user: dict = Depends(require_not_cashier)):
    doc = payload.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.clients.insert_one(doc)
    await write_audit(user, "create", "client", doc["id"], {"full_name": doc["full_name"]})
    doc.pop("_id", None)
    return doc


@api.get("/clients/{cid}")
async def get_client(cid: str, _: dict = Depends(get_current_user)):
    c = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return c


@api.get("/clients/{cid}/contracts")
async def client_contracts(cid: str, _: dict = Depends(get_current_user)):
    rows = await db.contracts.find({"client_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(500)
    out = []
    for r in rows:
        out.append(await _recompute_contract_status(r))
    return out


@api.get("/clients/{cid}/payments")
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


@api.put("/clients/{cid}")
async def update_client(cid: str, payload: ClientIn, _: dict = Depends(get_current_user)):
    res = await db.clients.update_one({"id": cid}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    c = await db.clients.find_one({"id": cid}, {"_id": 0})
    return c


@api.delete("/clients/{cid}")
async def delete_client(cid: str, _: dict = Depends(require_admin)):
    res = await db.clients.delete_one({"id": cid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"ok": True}


# =====================================================================
# Member ID Cards — issue / renew / revoke / verify / PDF
# =====================================================================
import secrets as _secrets  # noqa: E402


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
    """Public URL a QR code should point to. Uses PUBLIC_BASE_URL env or falls
    back to the API host — the frontend catches `/verify/:token` and calls the
    backend `/api/public/verify/:token` endpoint."""
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


@api.post("/clients/{cid}/issue-card")
async def issue_member_card(cid: str, user: dict = Depends(require_not_cashier)):
    client = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Only assign a new member_no if the client has never had a card
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


@api.post("/clients/{cid}/renew-card")
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


@api.post("/clients/{cid}/revoke-card")
async def revoke_member_card(cid: str, user: dict = Depends(require_admin)):
    client = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.get("member_no"):
        raise HTTPException(status_code=400, detail="No card issued")
    await db.clients.update_one({"id": cid}, {"$set": {"member_status": "revoked"}})
    await write_audit(user, "revoke_card", "client", cid, {"member_no": client.get("member_no")})
    return {"ok": True, "member_status": "revoked"}


@api.get("/clients/{cid}/card-pdf")
async def member_card_pdf(cid: str, _: dict = Depends(require_module("clients"))):
    client = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.get("member_no") or not client.get("member_verify_token"):
        raise HTTPException(status_code=400, detail="No card issued yet — issue first")
    # Reflect live status in the PDF (expired/revoked banner)
    client["member_status"] = _card_status(client)
    # Load the photo bytes directly from object storage if `photo_url` is a
    # storage key or `/api/files/...` path — the PDF generator can't call the
    # protected `/api/files` endpoint from inside the process (no cookie).
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


@api.get("/public/verify/{token}/photo")
async def public_verify_member_photo(token: str):
    """Public — streams the client's photo for the given verify token so QR-scan
    visitors (anonymous) can see the member photo without needing auth."""
    if not token or len(token) < 8:
        raise HTTPException(status_code=404, detail="Not found")
    client = await db.clients.find_one({"member_verify_token": token}, {"_id": 0})
    if not client or not client.get("photo_url"):
        raise HTTPException(status_code=404, detail="No photo")
    photo = str(client["photo_url"]).strip()
    if photo.lower().startswith(("http://", "https://")):
        # Absolute URL — redirect the browser to it
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


@api.get("/public/verify/{token}")
async def public_verify_member(token: str):
    """Public — anyone with the token (from QR scan) can verify the card."""
    if not token or len(token) < 8:
        raise HTTPException(status_code=404, detail="Not found")
    client = await db.clients.find_one({"member_verify_token": token}, {"_id": 0})
    if not client:
        return {"valid": False, "status": "not_found"}
    status = _card_status(client)
    # For QR-scan visitors (no auth), always link the photo through the public
    # verify-photo endpoint. This works for both absolute URLs (redirects) and
    # storage keys (streamed via objstore) without requiring auth cookies.
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


# =====================================================================
# Items — separate collections for car / motorcycle / electronic
# =====================================================================
# ITEM_KINDS imported from services

PEZADU_CATEGORIES = {"forklift", "tractor", "loader", "heavy_duty_truck"}


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
    market_value: float = 0.0
    location: str = ""  # warehouse / shop / off-site
    photo_url: str = ""
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
    market_value: float = 0.0
    location: str = ""
    photo_url: str = ""
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
    document_url: str = ""


def _item_model(kind: str):
    return {
        "car": CarIn,
        "motorcycle": MotorcycleIn,
        "electronic": ElectronicIn,
        "pezadu": PezaduIn,
    }[kind]


@api.get("/items/{kind}")
async def list_items(kind: str, _: dict = Depends(require_module("items"))):
    if kind not in ITEM_KINDS:
        raise HTTPException(status_code=400, detail="Invalid item kind")
    coll = db[COLLECTION_MAP[kind]]
    items = await coll.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@api.post("/items/{kind}")
async def create_item(kind: str, payload: dict, user: dict = Depends(require_not_cashier)):
    if kind not in ITEM_KINDS:
        raise HTTPException(status_code=400, detail="Invalid item kind")
    model = _item_model(kind)
    try:
        validated = model(**payload).model_dump()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    doc = {**validated, "id": new_id(), "kind": kind, "status": "in_stock",
           "created_at": utcnow_iso()}
    await db[COLLECTION_MAP[kind]].insert_one(doc)
    await write_audit(user, "create", f"item.{kind}", doc["id"], {"brand": doc.get("brand"), "model": doc.get("model")})
    doc.pop("_id", None)
    return doc


@api.get("/items/{kind}/{iid}")
async def get_item(kind: str, iid: str, _: dict = Depends(get_current_user)):
    if kind not in ITEM_KINDS:
        raise HTTPException(status_code=400, detail="Invalid item kind")
    it = await db[COLLECTION_MAP[kind]].find_one({"id": iid}, {"_id": 0})
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    return it


@api.put("/items/{kind}/{iid}")
async def update_item(kind: str, iid: str, payload: dict, _: dict = Depends(get_current_user)):
    if kind not in ITEM_KINDS:
        raise HTTPException(status_code=400, detail="Invalid item kind")
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


@api.delete("/items/{kind}/{iid}")
async def delete_item(kind: str, iid: str, _: dict = Depends(require_admin)):
    if kind not in ITEM_KINDS:
        raise HTTPException(status_code=400, detail="Invalid item kind")
    res = await db[COLLECTION_MAP[kind]].delete_one({"id": iid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


async def _fetch_item_LOCAL_DEAD(kind: str, iid: str) -> Optional[dict]:
    # dead stub — kept only as a marker; real impl lives in services.py
    return None


# =====================================================================
# Settings (single document) — DEFAULT_SETTINGS + get_settings_doc + _decrypted_settings
# have moved to services.py. Only the API models + endpoints remain here.
# =====================================================================
class SettingsIn(BaseModel):
    interest_rate_car: int = 10
    interest_rate_motorcycle: int = 15
    interest_rate_electronic: int = 15
    interest_rate_pezadu: int = 10
    warehouse_password: str = ""
    terms_and_conditions_en: str = ""
    terms_and_conditions_tet: str = ""
    whatsapp_template_en: str = ""
    whatsapp_template_tet: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    reminder_days_before: int = 3
    reminders_enabled: bool = True  # Master switch for daily overdue reminders (iter17)


@api.get("/settings")
async def settings_get(_: dict = Depends(get_current_user)):
    s = await get_settings_doc()
    # Mask the encrypted token before returning to the client; never expose plaintext
    from encryption import mask_token, is_configured as _is_configured
    enc = s.get("whatsapp_token", "")
    s["whatsapp_token"] = ""
    s["whatsapp_token_masked"] = mask_token(enc)
    s["whatsapp_connected"] = _is_configured(enc) and bool(s.get("whatsapp_phone_id"))
    # Warehouse lock status — do not expose the hash
    s["warehouse_locked"] = bool(s.pop("warehouse_password_hash", None))
    s["warehouse_password"] = ""
    return s


@api.put("/settings")
async def settings_put(payload: SettingsIn, admin: dict = Depends(require_admin)):
    from encryption import encrypt_token
    from auth import hash_password
    update = payload.model_dump()
    # Token handling: empty string = preserve existing, masked placeholder = preserve, otherwise re-encrypt
    new_token = (update.get("whatsapp_token") or "").strip()
    if new_token and "•" not in new_token:
        update["whatsapp_token"] = encrypt_token(new_token)
    else:
        update.pop("whatsapp_token", None)
    # Warehouse password: empty = preserve existing, otherwise hash
    new_pwd = (update.pop("warehouse_password", "") or "").strip()
    if new_pwd:
        update["warehouse_password_hash"] = hash_password(new_pwd)
    await db.settings.update_one(
        {"id": "singleton"},
        {"$set": update},
        upsert=True,
    )
    await write_audit(admin, "update", "settings", "singleton", {k: ("***" if k in ("whatsapp_token", "warehouse_password_hash") else v) for k, v in update.items()})
    return await settings_get(_=admin)


async def _decrypted_settings_LOCAL_DEAD() -> dict:
    """DEAD — moved to services.py._decrypted_settings"""
    return {}


# =====================================================================
# Contracts
# =====================================================================
class ContractIn(BaseModel):
    client_id: str
    item_id: str
    item_type: Literal["car", "motorcycle", "electronic", "pezadu"]
    loan_amount: float
    interest_rate: Optional[Literal[10, 15]] = None  # derived from settings by item_type when omitted
    contract_date: str  # YYYY-MM-DD
    due_date: str       # YYYY-MM-DD
    notes: str = ""


async def _generate_contract_number() -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"CTR-{year}-"
    # find highest sequence for this year
    last = await db.contracts.find({"contract_number": {"$regex": f"^{prefix}"}}) \
        .sort("contract_number", -1).limit(1).to_list(1)
    if last:
        try:
            seq = int(last[0]["contract_number"].split("-")[-1]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"




@api.get("/contracts")
async def list_contracts(_: dict = Depends(require_module("contracts"))):
    contracts = await db.contracts.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    out = []
    for c in contracts:
        c = await _recompute_contract_status(c)
        out.append(c)
    return out


@api.post("/contracts")
async def create_contract(payload: ContractIn, user: dict = Depends(require_not_cashier)):
    client_doc = await db.clients.find_one({"id": payload.client_id}, {"_id": 0})
    if not client_doc:
        raise HTTPException(status_code=404, detail="Client not found")
    item = await _fetch_item(payload.item_type, payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.get("status") not in ("in_stock", None):
        raise HTTPException(status_code=400, detail="Item is not available")
    # Max 2 months between contract date and due date
    try:
        cd = date.fromisoformat(payload.contract_date)
        dd = date.fromisoformat(payload.due_date)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid date format (YYYY-MM-DD)")
    if dd < cd:
        raise HTTPException(status_code=422, detail="Due date must be after contract date")
    days = (dd - cd).days
    if days > 62:  # ~2 months
        raise HTTPException(status_code=422, detail="Contract term cannot exceed 2 months")
    contract_number = await _generate_contract_number()
    doc = payload.model_dump()
    # Default interest by item type from settings
    if not doc.get("interest_rate"):
        sett = await get_settings_doc()
        defaults = {
            "car": sett.get("interest_rate_car", 10),
            "motorcycle": sett.get("interest_rate_motorcycle", 15),
            "electronic": sett.get("interest_rate_electronic", 15),
            "pezadu": sett.get("interest_rate_pezadu", 10),
        }
        doc["interest_rate"] = defaults[payload.item_type]
    doc["id"] = new_id()
    doc["contract_number"] = contract_number
    doc["status"] = "active"
    # Contracts created from Feb 2026 onward use Rule M1 (interest first, then
    # principal) so partial payments correctly reduce next-month interest.
    # Legacy contracts (pre-refactor) default to M2 via services.py logic.
    doc["interest_rule"] = "M1"
    doc["created_at"] = utcnow_iso()
    await db.contracts.insert_one(doc)
    # mark item as pawned
    await db[COLLECTION_MAP[payload.item_type]].update_one(
        {"id": payload.item_id},
        {"$set": {"status": "pawned", "active_contract_id": doc["id"]}},
    )
    # Auto-record loan DISBURSEMENT — client received the cash at signing
    disb_receipt = await _generate_receipt_number()
    disbursement = {
        "id": new_id(),
        "receipt_number": disb_receipt,
        "contract_id": doc["id"],
        "contract_number": contract_number,
        "amount": float(doc["loan_amount"]),
        "type": "disbursement",
        "date": doc["contract_date"],
        "notes": "Loan disbursed to client at contract signing",
        "created_at": utcnow_iso(),
        "created_by": user["id"],
    }
    await db.payments.insert_one(disbursement)
    await write_audit(user, "create", "contract", doc["id"], {"contract_number": contract_number, "loan_amount": doc["loan_amount"], "disbursement_receipt": disb_receipt})
    doc.pop("_id", None)
    return await _recompute_contract_status(doc)


class ReactivateIn(BaseModel):
    new_due_date: str  # YYYY-MM-DD
    notes: str = ""


@api.post("/contracts/{cid}/reactivate")
async def reactivate_contract(cid: str, payload: ReactivateIn, user: dict = Depends(require_not_cashier)):
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    c = await _recompute_contract_status(c)
    if c["status"] not in ("overdue", "active", "auction_ready"):
        raise HTTPException(status_code=400, detail="Only overdue or active contracts can be reactivated")
    try:
        nd = date.fromisoformat(payload.new_due_date)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid date")
    if nd <= date.today():
        raise HTTPException(status_code=422, detail="New due date must be in the future")
    if (nd - date.today()).days > 62:
        raise HTTPException(status_code=422, detail="Reactivated term cannot exceed 2 months from today")
    await db.contracts.update_one(
        {"id": cid},
        {"$set": {"due_date": payload.new_due_date, "status": "active",
                  "reactivated_at": utcnow_iso(), "reactivate_notes": payload.notes}},
    )
    await write_audit(user, "reactivate", "contract", cid, {"new_due_date": payload.new_due_date})
    refreshed = await db.contracts.find_one({"id": cid}, {"_id": 0})
    return await _recompute_contract_status(refreshed)


@api.get("/contracts/{cid}")
async def get_contract(cid: str, _: dict = Depends(get_current_user)):
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    return await _recompute_contract_status(c)


@api.delete("/contracts/{cid}")
async def delete_contract(cid: str, _: dict = Depends(require_admin)):
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    await db.payments.delete_many({"contract_id": cid})
    await db.contracts.delete_one({"id": cid})
    # release item back to stock
    await db[COLLECTION_MAP[c["item_type"]]].update_one(
        {"id": c["item_id"]},
        {"$set": {"status": "in_stock"}, "$unset": {"active_contract_id": ""}},
    )
    return {"ok": True}


@api.get("/contracts/{cid}/pdf")
async def contract_pdf(cid: str, _: dict = Depends(get_current_user)):
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    c = await _recompute_contract_status(c)
    client_doc = await db.clients.find_one({"id": c["client_id"]}, {"_id": 0}) or {}
    item = await _fetch_item(c["item_type"], c["item_id"]) or {}
    sett = await get_settings_doc()
    pdf_bytes = build_contract_pdf(c, client_doc, item, sett)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{c["contract_number"]}.pdf"'},
    )


@api.get("/contracts/{cid}/terms-card")
async def contract_terms_card(cid: str, _: dict = Depends(get_current_user)):
    """Personalized "Terms of your Loan" one-pager — printed alongside the
    contract at signing so the client acknowledges the interest math IN
    WRITING with their exact numbers filled in."""
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    client_doc = await db.clients.find_one({"id": c["client_id"]}, {"_id": 0}) or {}
    item = await _fetch_item(c["item_type"], c["item_id"]) or {}
    pdf_bytes = build_loan_terms_card_pdf(c, client_doc, item)
    fname = f'{c.get("contract_number", "contract")}-terms.pdf'
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


# =====================================================================
# Payments
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


@api.get("/payments")
async def list_payments(contract_id: Optional[str] = None, _: dict = Depends(require_module("payments"))):
    q = {"contract_id": contract_id} if contract_id else {}
    items = await db.payments.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@api.post("/payments")
async def create_payment(payload: PaymentIn, user: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    # Payment date must be between contract date and today (or due date — clients may pay anytime)
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
        # release item
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
    return {"payment": doc, "contract": updated}


@api.get("/payments/{pid}/pdf")
async def payment_pdf(pid: str, _: dict = Depends(get_current_user)):
    p = await db.payments.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    c = await db.contracts.find_one({"id": p["contract_id"]}, {"_id": 0}) or {}
    c = await _recompute_contract_status(c) if c else {}
    client_doc = await db.clients.find_one({"id": c.get("client_id")}, {"_id": 0}) or {}
    # Also load the pawned item so we can show its description in the receipt (esp. for disbursement)
    item_doc = {}
    if c.get("item_type") and c.get("item_id"):
        item_doc = await _fetch_item(c["item_type"], c["item_id"]) or {}
    pdf_bytes = build_receipt_pdf(p, c, client_doc, c.get("remaining_balance", 0), item=item_doc)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{p["receipt_number"]}.pdf"'},
    )


@api.delete("/payments/{pid}")
async def delete_payment(pid: str, user: dict = Depends(require_admin)):
    """Admin-only: delete a payment record. If it was a disbursement, the
    contract balance goes back up; if it was a regular repayment, it goes down
    again. Contract status is recomputed automatically."""
    payment = await db.payments.find_one({"id": pid}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    res = await db.payments.delete_one({"id": pid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Payment not found")
    # Recompute contract if it still exists
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


# =====================================================================
# Auctions
# =====================================================================
class AuctionMoveIn(BaseModel):
    contract_id: str
    starting_price: float = 0.0


class AuctionSoldIn(BaseModel):
    sold_price: float
    interest_fee: Optional[float] = None  # if None, computed from contract outstanding interest+penalty
    buyer_name: str = ""
    buyer_phone: str = ""
    buyer_email: str = ""
    buyer_address: str = ""
    buyer_id_number: str = ""
    tax_percent: float = 0.0
    notes: str = ""


@api.get("/auctions")
async def list_auctions(_: dict = Depends(require_module("auctions"))):
    items = await db.auctions.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@api.get("/auctions/public")
async def public_auctions():
    items = await db.auctions.find({"status": "listed"}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # enrich with item details
    out = []
    for a in items:
        item = await _fetch_item(a["item_type"], a["item_id"]) or {}
        out.append({**a, "item": item})
    return out


@api.post("/auctions/move")
async def move_to_auction(payload: AuctionMoveIn, _: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    contract = await _recompute_contract_status(contract)
    if contract["status"] not in ("overdue", "active", "auction_ready"):
        raise HTTPException(status_code=400, detail="Only active/overdue contracts can be auctioned")
    doc = {
        "id": new_id(),
        "contract_id": contract["id"],
        "contract_number": contract["contract_number"],
        "item_id": contract["item_id"],
        "item_type": contract["item_type"],
        "starting_price": payload.starting_price,
        "status": "listed",
        "created_at": utcnow_iso(),
    }
    await db.auctions.insert_one(doc)
    await db.contracts.update_one({"id": contract["id"]}, {"$set": {"status": "auction"}})
    await db[COLLECTION_MAP[contract["item_type"]]].update_one(
        {"id": contract["item_id"]},
        {"$set": {"status": "auction"}},
    )
    doc.pop("_id", None)
    return doc


async def _generate_invoice_number() -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"INV-{year}-"
    last = await db.invoices.find({"invoice_number": {"$regex": f"^{prefix}"}}) \
        .sort("invoice_number", -1).limit(1).to_list(1)
    if last:
        try:
            seq = int(last[0]["invoice_number"].split("-")[-1]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


@api.post("/auctions/{aid}/sold")
async def mark_sold(aid: str, payload: AuctionSoldIn, user: dict = Depends(require_not_cashier)):
    a = await db.auctions.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    if a.get("status") == "sold" and a.get("invoice_id"):
        # Idempotent — return existing invoice instead of minting a duplicate
        existing = await db.invoices.find_one({"id": a["invoice_id"]}, {"_id": 0})
        if existing:
            return {**a, "invoice": existing}

    # Compute interest_fee — defaults to outstanding interest + penalty on the contract
    contract = await db.contracts.find_one({"id": a.get("contract_id")}, {"_id": 0}) or {}
    if contract:
        contract = await _recompute_contract_status(contract)
    if payload.interest_fee is None:
        default_fee = float(contract.get("interest_remaining", 0)) + float(contract.get("penalty", 0))
        interest_fee = round(default_fee, 2)
    else:
        interest_fee = round(float(payload.interest_fee), 2)
    # Internal split: portion of sold_price counted as interest (profit), rest as cash recovery
    sold_price = float(payload.sold_price)
    interest_fee = min(interest_fee, sold_price)  # cannot exceed sold price
    cash_portion = round(sold_price - interest_fee, 2)

    update = {
        "status": "sold",
        "sold_price": sold_price,
        "interest_fee": interest_fee,        # NEW — separated for finance
        "cash_portion": cash_portion,        # NEW — sold_price - interest_fee
        "buyer_name": payload.buyer_name,
        "buyer_phone": payload.buyer_phone,
        "buyer_email": payload.buyer_email,
        "buyer_address": payload.buyer_address,
        "buyer_id_number": payload.buyer_id_number,
        "sold_at": utcnow_iso(),
        "notes": payload.notes,
    }
    await db.auctions.update_one({"id": aid}, {"$set": update})
    await db[COLLECTION_MAP[a["item_type"]]].update_one(
        {"id": a["item_id"]},
        {"$set": {"status": "sold"}},
    )
    # Auto-create invoice — buyer sees only item + sold_price + tax + total (NO interest line)
    inv_number = await _generate_invoice_number()
    subtotal = sold_price
    tax = round(subtotal * float(payload.tax_percent or 0) / 100.0, 2)
    invoice = {
        "id": new_id(),
        "invoice_number": inv_number,
        "auction_id": aid,
        "contract_number": a.get("contract_number"),
        "item_type": a["item_type"],
        "item_id": a["item_id"],
        "buyer_name": payload.buyer_name,
        "buyer_phone": payload.buyer_phone,
        "buyer_email": payload.buyer_email,
        "buyer_address": payload.buyer_address,
        "buyer_id_number": payload.buyer_id_number,
        "subtotal": round(subtotal, 2),
        "tax_percent": float(payload.tax_percent or 0),
        "tax_amount": tax,
        "total": round(subtotal + tax, 2),
        # Internal-only fields for accounting; NOT shown on buyer invoice PDF
        "_internal_interest_fee": interest_fee,
        "_internal_cash_portion": cash_portion,
        "status": "issued",
        "date": date.today().isoformat(),
        "notes": payload.notes,
        "created_at": utcnow_iso(),
        "created_by": user["id"],
    }
    await db.invoices.insert_one(invoice)
    await db.auctions.update_one({"id": aid}, {"$set": {"invoice_id": invoice["id"], "invoice_number": inv_number}})
    await write_audit(user, "sold_auction", "auction", aid, {"sold_price": sold_price, "interest_fee": interest_fee, "invoice_number": inv_number})
    invoice.pop("_id", None)
    return {**a, **update, "invoice_id": invoice["id"], "invoice_number": inv_number, "invoice": invoice}


# =====================================================================
# Invoices
# =====================================================================
class InvoiceUpdateIn(BaseModel):
    buyer_name: Optional[str] = None
    buyer_phone: Optional[str] = None
    buyer_email: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_id_number: Optional[str] = None
    tax_percent: Optional[float] = None
    status: Optional[Literal["issued", "paid", "cancelled"]] = None
    notes: Optional[str] = None


@api.get("/invoices")
async def list_invoices(_: dict = Depends(get_current_user)):
    return await db.invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)


@api.get("/invoices/{iid}")
async def get_invoice(iid: str, _: dict = Depends(get_current_user)):
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@api.put("/invoices/{iid}")
async def update_invoice(iid: str, payload: InvoiceUpdateIn, user: dict = Depends(require_not_cashier)):
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    update = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "tax_percent" in update:
        sub = float(inv["subtotal"])
        tax = round(sub * float(update["tax_percent"]) / 100.0, 2)
        update["tax_amount"] = tax
        update["total"] = round(sub + tax, 2)
    await db.invoices.update_one({"id": iid}, {"$set": update})
    await write_audit(user, "update", "invoice", iid, update)
    return await db.invoices.find_one({"id": iid}, {"_id": 0})


@api.get("/invoices/export/pdf")
async def invoices_list_pdf(_: dict = Depends(get_current_user)):
    invoices = await db.invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    pdf_bytes = build_invoices_list_pdf(invoices)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="invoices.pdf"'},
    )


@api.get("/invoices/{iid}/pdf")
async def invoice_pdf(iid: str, _: dict = Depends(get_current_user)):
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    item = await _fetch_item(inv["item_type"], inv["item_id"]) or {}
    pdf_bytes = build_invoice_pdf(inv, item)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{inv["invoice_number"]}.pdf"'},
    )


@api.delete("/auctions/{aid}")
async def delete_auction(aid: str, user: dict = Depends(require_admin)):
    """Admin-only: remove an auction listing. If the auction was still 'listed'
    (not sold), we also flip the underlying contract back to 'overdue' so it
    doesn't stay stuck in the 'auction' state. Sold auctions are only removed
    if the caller confirms — but we still cascade so the finance/invoice stays
    consistent."""
    a = await db.auctions.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    res = await db.auctions.delete_one({"id": aid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found")
    # Revert contract status so the workflow doesn't get stuck
    if a.get("contract_id"):
        contract = await db.contracts.find_one({"id": a["contract_id"]}, {"_id": 0})
        if contract:
            # Only revert if the contract is still in "auction" state (i.e. the auction
            # hadn't been sold and reconciled). Otherwise leave it alone.
            if contract.get("status") in ("auction", "auction_ready"):
                await db.contracts.update_one(
                    {"id": contract["id"]},
                    {"$set": {"status": "overdue"}, "$unset": {"auction_id": ""}},
                )
    await write_audit(user, "delete", "auction", aid, {
        "contract_id": a.get("contract_id"),
        "contract_number": a.get("contract_number"),
        "status": a.get("status"),
    })
    return {"ok": True}


# =====================================================================
# Dashboard
# =====================================================================
@api.get("/dashboard/summary")
async def dashboard_summary(_: dict = Depends(require_module("dashboard"))):
    contracts = await db.contracts.find({}, {"_id": 0}).to_list(5000)
    payments = await db.payments.find({}, {"_id": 0}).to_list(5000)
    clients_count = await db.clients.count_documents({})

    active = overdue = redeemed = auction = 0
    total_loan = 0.0
    total_interest = 0.0
    today = _today_iso()
    for c in contracts:
        loan = float(c.get("loan_amount", 0))
        rate = float(c.get("interest_rate", 0))
        total_loan += loan
        total_interest += loan * rate / 100.0
        status = c.get("status", "active")
        if status in ("redeemed",):
            redeemed += 1
        elif status == "auction":
            auction += 1
        elif c.get("due_date", today) < today and status != "redeemed":
            overdue += 1
        else:
            active += 1

    total_payments = sum(float(p["amount"]) for p in payments)
    profit = total_payments - sum(
        float(c.get("loan_amount", 0)) for c in contracts if c.get("status") == "redeemed"
    )

    return {
        "total_clients": clients_count,
        "active_contracts": active,
        "overdue_contracts": overdue,
        "redeemed_contracts": redeemed,
        "auction_contracts": auction,
        "total_loan_amount": round(total_loan, 2),
        "total_interest_expected": round(total_interest, 2),
        "total_payments": round(total_payments, 2),
        "profit": round(profit, 2),
    }


# =====================================================================



# =====================================================================
# Dashboard trends (for charts)
# =====================================================================
@api.get("/dashboard/trends")
async def dashboard_trends(_: dict = Depends(get_current_user)):
    """Return last-6-month monthly aggregates and overdue snapshot."""
    contracts = await db.contracts.find({}, {"_id": 0}).to_list(5000)
    payments = await db.payments.find({}, {"_id": 0}).to_list(5000)
    # Build last 6 buckets (YYYY-MM)
    today = date.today()
    buckets = []
    for i in range(5, -1, -1):
        # back i months
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12
            y -= 1
        buckets.append(f"{y:04d}-{m:02d}")
    by_month = {b: {"month": b, "loans": 0.0, "payments": 0.0, "interest": 0.0} for b in buckets}
    for c in contracts:
        ym = (c.get("contract_date") or "")[:7]
        if ym in by_month:
            loan = float(c.get("loan_amount", 0) or 0)
            rate = float(c.get("interest_rate", 0) or 0)
            by_month[ym]["loans"] += loan
            by_month[ym]["interest"] += loan * rate / 100.0
    for p in payments:
        ym = (p.get("date") or "")[:7]
        if ym in by_month:
            by_month[ym]["payments"] += float(p.get("amount", 0) or 0)
    months = [
        {**v, "loans": round(v["loans"], 2),
         "payments": round(v["payments"], 2),
         "interest": round(v["interest"], 2)}
        for v in by_month.values()
    ]
    # Overdue counts grouped by status snapshot per item type
    by_type = {"car": 0, "motorcycle": 0, "electronic": 0, "pezadu": 0}
    today_iso = _today_iso()
    for c in contracts:
        if c.get("status") in ("redeemed", "sold"):
            continue
        if (c.get("due_date") or "") < today_iso and c.get("status") != "auction":
            by_type[c.get("item_type", "car")] = by_type.get(c.get("item_type", "car"), 0) + 1
    overdue_by_type = [{"type": k, "count": v} for k, v in by_type.items()]
    return {"months": months, "overdue_by_type": overdue_by_type}


# =====================================================================
# File uploads (object storage)
# =====================================================================
ALLOWED_MIME = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif",
    "application/pdf", "application/octet-stream",
}


@api.post("/upload")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if file.content_type and file.content_type not in ALLOWED_MIME and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (15MB max)")
    ext = (file.filename or "bin").split(".")[-1].lower()
    app_name = os.environ.get("APP_NAME", "fatin-penhores")
    path = f"{app_name}/uploads/{user['id']}/{new_id()}.{ext}"
    try:
        result = objstore.put_object(path, data, file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    record = {
        "id": new_id(),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "uploaded_by": user["id"],
        "created_at": utcnow_iso(),
    }
    await db.files.insert_one(record)
    record.pop("_id", None)
    # Frontend-friendly download URL (relative path)
    record["url"] = f"/api/files/{result['path']}"
    return record


@api.get("/files/{path:path}")
async def download_file(path: str, request: Request, auth: Optional[str] = Query(None)):
    # Allow either cookie auth (default) or ?auth=<access_token> query param for <img> tags
    if auth and not request.cookies.get("access_token"):
        # Inject token into request cookies for dependency
        request.scope.setdefault("headers", [])
        request._cookies = {"access_token": auth, **request.cookies}  # type: ignore
    # Verify user via cookie/header
    token = request.cookies.get("access_token") or auth
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    record = await db.files.find_one({"storage_path": path, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, content_type = objstore.get_object(path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    return Response(content=data, media_type=record.get("content_type") or content_type)


@api.delete("/files/{file_id}")
async def delete_file(file_id: str, _: dict = Depends(require_admin)):
    await db.files.update_one({"id": file_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}




app.include_router(api)

# Domain routers extracted from server.py (Phase 2 refactor)
from routes.reports import router as reports_router  # noqa: E402
from routes.finance import router as finance_router  # noqa: E402
from routes.public import router as public_router  # noqa: E402
from routes.whatsapp import router as whatsapp_router  # noqa: E402
from routes.admin import router as admin_router  # noqa: E402
from routes.auth_extra import router as auth_extra_router  # noqa: E402
from routes.monthend import router as monthend_router  # noqa: E402
from routes.report_views import router as report_views_router  # noqa: E402
app.include_router(reports_router, prefix="/api")
app.include_router(finance_router, prefix="/api")
app.include_router(public_router, prefix="/api")
app.include_router(whatsapp_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(auth_extra_router, prefix="/api")
app.include_router(monthend_router, prefix="/api")
app.include_router(report_views_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# Startup — seed admin + indexes
# =====================================================================
@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.clients.create_index("id", unique=True)
    await db.contracts.create_index("id", unique=True)
    await db.contracts.create_index("contract_number", unique=True)
    await db.payments.create_index("id", unique=True)
    await db.payments.create_index("receipt_number", unique=True)
    await db.audit_log.create_index("created_at")
    await db.audit_log.create_index("resource")
    await db.audit_log.create_index("action")
    await db.audit_log.create_index("actor_email")
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index("user_id")
    await db.files.create_index("id", unique=True)
    await db.files.create_index("storage_path")
    await db.invoices.create_index("id", unique=True)
    await db.invoices.create_index("invoice_number", unique=True)
    for coll in COLLECTION_MAP.values():
        await db[coll].create_index("id", unique=True)

    # Initialize object storage (best-effort)
    try:
        objstore.init_storage()
    except Exception as e:
        logger.warning(f"Object storage not initialized: {e}")

    # Seed settings
    await get_settings_doc()

    # Backfill allowed_modules on existing users that don't have it yet (iter11)
    async for u in db.users.find({"allowed_modules": {"$exists": False}}, {"_id": 0, "id": 1, "role": 1}):
        defaults = ROLE_DEFAULT_MODULES.get(u.get("role"), [])
        if u.get("role") == "admin":
            defaults = list(ALL_MODULES)
        await db.users.update_one({"id": u["id"]}, {"$set": {"allowed_modules": defaults}})

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@fatinpenhores.tl").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": new_id(),
            "email": admin_email,
            "name": "Administrator",
            "role": "admin",
            "allowed_modules": list(ALL_MODULES),
            "password_hash": hash_password(admin_password),
            "created_at": utcnow_iso(),
        })
        logger.info(f"Seeded admin: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password), "allowed_modules": list(ALL_MODULES)}},
        )
        logger.info(f"Updated admin password for: {admin_email}")

    # Daily scheduled tasks (backup + prune)
    try:
        from scheduler import start_scheduler
        start_scheduler()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Scheduler did not start: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        from scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:  # noqa: BLE001
        pass
    # Motor client is owned by deps.py — close via its internal reference
    from deps import _client as _mongo_client
    _mongo_client.close()
