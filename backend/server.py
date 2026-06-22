"""Fatin Penhores Pawn System — FastAPI backend."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, UploadFile, File, Form, Query, Header
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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
    build_receipt_pdf,
    DEFAULT_TNC_EN,
    DEFAULT_TNC_TET,
)
import storage as objstore
import whatsapp as wapp

# ---- Setup ----
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Fatin Penhores Pawn System")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fatin")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# =====================================================================
# Auth — JWT via httpOnly cookies
# =====================================================================
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_roles(*allowed: str):
    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires role in {allowed}")
        return user
    return _dep


# ---- Audit logging ----
async def write_audit(actor: dict, action: str, resource: str, resource_id: str | None = None, payload: dict | None = None):
    try:
        await db.audit_log.insert_one({
            "id": new_id(),
            "actor_id": actor.get("id"),
            "actor_email": actor.get("email"),
            "actor_role": actor.get("role"),
            "action": action,
            "resource": resource,
            "resource_id": resource_id or "",
            "payload": payload or {},
            "created_at": utcnow_iso(),
        })
    except Exception as e:  # never block primary operation due to logging
        logger.warning(f"audit log failed: {e}")


@api.post("/auth/login")
async def auth_login(payload: LoginIn, response: Response):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}


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
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"ok": True}


# Helpers for role gates
require_not_cashier = require_roles("admin", "staff")


# =====================================================================
# Users (admin manages staff)
# =====================================================================
class UserCreateIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["admin", "staff", "cashier"] = "staff"


@api.get("/users")
async def list_users(_: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users


@api.post("/users")
async def create_user(payload: UserCreateIn, _: dict = Depends(require_admin)):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already exists")
    doc = {
        "id": new_id(),
        "email": email,
        "name": payload.name,
        "role": payload.role,
        "password_hash": hash_password(payload.password),
        "created_at": utcnow_iso(),
    }
    await db.users.insert_one(doc)
    doc.pop("password_hash")
    doc.pop("_id", None)
    return doc


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
async def list_clients(_: dict = Depends(get_current_user)):
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
# Items — separate collections for car / motorcycle / electronic
# =====================================================================
ITEM_KINDS = {"car", "motorcycle", "electronic"}
COLLECTION_MAP = {"car": "cars", "motorcycle": "motorcycles", "electronic": "electronics"}


class CarIn(BaseModel):
    brand: str
    model: str
    description: str = ""
    plate: str = ""
    chassis: str = ""
    fuel_percent: int = 0
    color: str = ""
    manufacture_year: Optional[int] = None
    market_value: float = 0.0
    location: str = ""  # warehouse / shop / off-site
    photo_url: str = ""
    document_url: str = ""


class MotorcycleIn(BaseModel):
    brand: str
    model: str
    description: str = ""
    plate: str = ""
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


def _item_model(kind: str):
    return {"car": CarIn, "motorcycle": MotorcycleIn, "electronic": ElectronicIn}[kind]


@api.get("/items/{kind}")
async def list_items(kind: str, _: dict = Depends(get_current_user)):
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


async def _fetch_item(kind: str, iid: str) -> Optional[dict]:
    if kind not in ITEM_KINDS:
        return None
    return await db[COLLECTION_MAP[kind]].find_one({"id": iid}, {"_id": 0})


# =====================================================================
# Settings (single document)
# =====================================================================
DEFAULT_SETTINGS = {
    "id": "singleton",
    "interest_rate_car": 10,
    "interest_rate_motorcycle": 15,
    "interest_rate_electronic": 15,
    "terms_and_conditions_en": DEFAULT_TNC_EN,
    "terms_and_conditions_tet": DEFAULT_TNC_TET,
    "whatsapp_template_en": "due_date_reminder",
    "whatsapp_template_tet": "due_date_reminder_tet",
    "whatsapp_token": "",
    "whatsapp_phone_id": "",
    "reminder_days_before": 3,
}


async def get_settings_doc() -> dict:
    doc = await db.settings.find_one({"id": "singleton"}, {"_id": 0})
    if not doc:
        await db.settings.insert_one(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()
    # Backfill defaults for any new keys
    merged = {**DEFAULT_SETTINGS, **doc}
    return merged


class SettingsIn(BaseModel):
    interest_rate_car: int = 10
    interest_rate_motorcycle: int = 15
    interest_rate_electronic: int = 15
    terms_and_conditions_en: str = ""
    terms_and_conditions_tet: str = ""
    whatsapp_template_en: str = ""
    whatsapp_template_tet: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    reminder_days_before: int = 3


@api.get("/settings")
async def settings_get(_: dict = Depends(get_current_user)):
    s = await get_settings_doc()
    # do not return token to non-admins
    return s


@api.put("/settings")
async def settings_put(payload: SettingsIn, admin: dict = Depends(require_admin)):
    update = payload.model_dump()
    await db.settings.update_one(
        {"id": "singleton"},
        {"$set": update},
        upsert=True,
    )
    await write_audit(admin, "update", "settings", "singleton", update)
    return await get_settings_doc()


# =====================================================================
# Contracts
# =====================================================================
class ContractIn(BaseModel):
    client_id: str
    item_id: str
    item_type: Literal["car", "motorcycle", "electronic"]
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


def _today_iso() -> str:
    return date.today().isoformat()


async def _recompute_contract_status(contract: dict) -> dict:
    """Compute live status, principal/interest split, and penalty."""
    payments = await db.payments.find({"contract_id": contract["id"]}, {"_id": 0}).to_list(500)
    loan = float(contract["loan_amount"])
    rate = float(contract["interest_rate"])
    interest = round(loan * rate / 100.0, 2)

    # Split payments into interest vs principal
    interest_paid = 0.0
    principal_paid = 0.0
    interest_remaining = interest
    for p in sorted(payments, key=lambda x: (x.get("date", ""), x.get("created_at", ""))):
        amt = float(p.get("amount", 0))
        ptype = p.get("type", "partial")
        if ptype == "interest_only":
            take = min(amt, max(0.0, interest - interest_paid))
            interest_paid += take
            # any excess flows to principal
            extra = amt - take
            if extra > 0:
                principal_paid += extra
        elif ptype == "partial":
            # partial pay reduces principal first per user rule
            principal_paid += amt
        elif ptype == "full":
            # split: cover interest first, then principal
            take = max(0.0, interest - interest_paid)
            interest_paid += min(amt, take)
            principal_paid += max(0.0, amt - take)

    principal_paid = min(principal_paid, loan)
    interest_paid = min(interest_paid, interest)
    principal_remaining = round(max(0.0, loan - principal_paid), 2)
    interest_remaining = round(max(0.0, interest - interest_paid), 2)

    # Penalty: 10% of original loan if overdue and not fully redeemed (does NOT include interest)
    today = _today_iso()
    is_overdue = contract.get("due_date", today) < today
    redeemed = (principal_remaining + interest_remaining) <= 0.01
    penalty = 0.0
    if is_overdue and not redeemed and contract.get("status") != "auction":
        penalty = round(loan * 0.10, 2)

    total_due = round(principal_remaining + interest_remaining + penalty, 2)

    # Status
    if contract.get("status") == "auction":
        status = "auction"
    elif contract.get("status") == "sold":
        status = "sold"
    elif redeemed:
        status = "redeemed"
    elif is_overdue:
        status = "overdue"
    else:
        status = "active"

    if status != contract.get("status"):
        await db.contracts.update_one({"id": contract["id"]}, {"$set": {"status": status}})

    contract["status"] = status
    contract["paid_amount"] = round(principal_paid + interest_paid, 2)
    contract["principal_paid"] = round(principal_paid, 2)
    contract["interest_paid"] = round(interest_paid, 2)
    contract["principal_remaining"] = principal_remaining
    contract["interest_remaining"] = interest_remaining
    contract["interest_amount"] = interest
    contract["penalty"] = penalty
    contract["total_due"] = total_due
    contract["remaining_balance"] = total_due
    return contract


@api.get("/contracts")
async def list_contracts(_: dict = Depends(get_current_user)):
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
        }
        doc["interest_rate"] = defaults[payload.item_type]
    doc["id"] = new_id()
    doc["contract_number"] = contract_number
    doc["status"] = "active"
    doc["created_at"] = utcnow_iso()
    await db.contracts.insert_one(doc)
    # mark item as pawned
    await db[COLLECTION_MAP[payload.item_type]].update_one(
        {"id": payload.item_id},
        {"$set": {"status": "pawned", "active_contract_id": doc["id"]}},
    )
    await write_audit(user, "create", "contract", doc["id"], {"contract_number": contract_number, "loan_amount": doc["loan_amount"]})
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
    if c["status"] not in ("overdue", "active"):
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


# =====================================================================
# Payments
# =====================================================================
class PaymentIn(BaseModel):
    contract_id: str
    amount: float
    type: Literal["full", "partial", "interest_only"]
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
async def list_payments(contract_id: Optional[str] = None, _: dict = Depends(get_current_user)):
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
    pdf_bytes = build_receipt_pdf(p, c, client_doc, c.get("remaining_balance", 0))
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{p["receipt_number"]}.pdf"'},
    )


# =====================================================================
# Auctions
# =====================================================================
class AuctionMoveIn(BaseModel):
    contract_id: str
    starting_price: float = 0.0


class AuctionSoldIn(BaseModel):
    sold_price: float
    buyer_name: str = ""
    notes: str = ""


@api.get("/auctions")
async def list_auctions(_: dict = Depends(get_current_user)):
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
    if contract["status"] not in ("overdue", "active"):
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


@api.post("/auctions/{aid}/sold")
async def mark_sold(aid: str, payload: AuctionSoldIn, _: dict = Depends(get_current_user)):
    a = await db.auctions.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    update = {
        "status": "sold",
        "sold_price": payload.sold_price,
        "buyer_name": payload.buyer_name,
        "sold_at": utcnow_iso(),
        "notes": payload.notes,
    }
    await db.auctions.update_one({"id": aid}, {"$set": update})
    await db[COLLECTION_MAP[a["item_type"]]].update_one(
        {"id": a["item_id"]},
        {"$set": {"status": "sold"}},
    )
    return {**a, **update}


@api.delete("/auctions/{aid}")
async def delete_auction(aid: str, _: dict = Depends(require_admin)):
    res = await db.auctions.delete_one({"id": aid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found")
    return {"ok": True}


# =====================================================================
# Dashboard
# =====================================================================
@api.get("/dashboard/summary")
async def dashboard_summary(_: dict = Depends(get_current_user)):
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
# Reports
# =====================================================================
# =====================================================================
# Reports — structured aggregations with filters + KPI cards
# =====================================================================
def _ym_from_iso(iso: str | None) -> tuple[int | None, int | None]:
    if not iso or len(iso) < 7:
        return None, None
    try:
        y = int(iso[:4])
        m = int(iso[5:7])
        return y, m
    except Exception:
        return None, None


def _apply_date_filter(rows: list[dict], date_field: str, month: Optional[int], year: Optional[int]) -> list[dict]:
    if not month and not year:
        return rows
    out = []
    for r in rows:
        y, m = _ym_from_iso(r.get(date_field))
        if year and y != year:
            continue
        if month and m != month:
            continue
        out.append(r)
    return out


def _apply_item_filter(rows: list[dict], category: Optional[str], sub_category: Optional[str]) -> list[dict]:
    """category = car/motorcycle/electronic; sub_category = electronic category (phone/laptop/...)."""
    if not category and not sub_category:
        return rows
    out = []
    for r in rows:
        if category and r.get("item_type") != category:
            continue
        if sub_category and r.get("item_category") != sub_category:
            continue
        out.append(r)
    return out


async def _enrich_contracts_with_item_meta(rows: list[dict]) -> list[dict]:
    """Add item_brand, item_model, item_category fields to each contract for filtering/display."""
    for r in rows:
        it = await _fetch_item(r.get("item_type", ""), r.get("item_id", ""))
        if it:
            r["item_brand"] = it.get("brand", "")
            r["item_model"] = it.get("model", "")
            r["item_category"] = it.get("category", "")
            r["item_location"] = it.get("location", "")
            r["item_market_value"] = float(it.get("market_value", 0) or 0)
    return rows


async def _enrich_payments_with_contract(rows: list[dict]) -> list[dict]:
    contract_ids = list({r["contract_id"] for r in rows if r.get("contract_id")})
    if not contract_ids:
        return rows
    contracts = await db.contracts.find({"id": {"$in": contract_ids}}, {"_id": 0}).to_list(5000)
    by_id = {c["id"]: c for c in contracts}
    for r in rows:
        c = by_id.get(r.get("contract_id"))
        if c:
            r["contract_number"] = c.get("contract_number")
            r["item_type"] = c.get("item_type")
            r["client_id"] = c.get("client_id")
    return rows


async def _report_active_contracts(filters: dict) -> dict:
    today = date.today()
    rows = await db.contracts.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    # recompute statuses (live)
    for r in rows:
        await _recompute_contract_status(r)
    rows = [r for r in rows if r.get("status") == "active"]
    rows = await _enrich_contracts_with_item_meta(rows)
    rows = _apply_date_filter(rows, "contract_date", filters.get("month"), filters.get("year"))
    rows = _apply_item_filter(rows, filters.get("category"), filters.get("sub_category"))
    total_contracts = len(rows)
    total_loan = sum(float(r.get("loan_amount", 0) or 0) for r in rows)
    tax_accumulate = sum(float(r.get("interest_amount", 0) or 0) for r in rows)
    near = today + timedelta(days=7)
    almost_expired = sum(
        1 for r in rows
        if r.get("due_date") and r["due_date"] <= near.isoformat() and r["due_date"] >= today.isoformat()
    )
    return {
        "kpis": {
            "total_contracts": total_contracts,
            "total_loan": round(total_loan, 2),
            "tax_accumulate": round(tax_accumulate, 2),
            "almost_expired": almost_expired,
        },
        "columns": ["contract_number", "item_type", "item_brand", "item_model", "loan_amount",
                    "interest_rate", "interest_amount", "contract_date", "due_date", "status"],
        "rows": rows,
    }


async def _report_payments(filters: dict) -> dict:
    rows = await db.payments.find({}, {"_id": 0}).sort("date", -1).to_list(5000)
    rows = await _enrich_payments_with_contract(rows)
    rows = _apply_date_filter(rows, "date", filters.get("month"), filters.get("year"))
    rows = _apply_item_filter(rows, filters.get("category"), filters.get("sub_category"))
    total_transactions = len(rows)
    total_payments = sum(float(r.get("amount", 0) or 0) for r in rows)
    # Interest received: amount classified as interest_only OR pro-rata of full payments
    # simple model: count amount where type=interest_only as interest; for partial keep as principal; for full keep min(amount, interest_amount)
    interest_received = 0.0
    for r in rows:
        amt = float(r.get("amount", 0) or 0)
        if r.get("type") == "interest_only":
            interest_received += amt
    # Total penalty: sum of penalty on overdue contracts narrowed by the same filters
    overdue_contracts = await db.contracts.find({"status": "overdue"}, {"_id": 0}).to_list(5000)
    for c in overdue_contracts:
        await _recompute_contract_status(c)
    overdue_contracts = await _enrich_contracts_with_item_meta(overdue_contracts)
    overdue_contracts = _apply_date_filter(overdue_contracts, "due_date", filters.get("month"), filters.get("year"))
    overdue_contracts = _apply_item_filter(overdue_contracts, filters.get("category"), filters.get("sub_category"))
    total_penalty = sum(float(c.get("penalty", 0) or 0) for c in overdue_contracts)
    return {
        "kpis": {
            "total_transactions": total_transactions,
            "total_payments": round(total_payments, 2),
            "interest_received": round(interest_received, 2),
            "total_penalty": round(total_penalty, 2),
        },
        "columns": ["receipt_number", "contract_number", "item_type", "type", "amount", "date"],
        "rows": rows,
    }


async def _report_overdue(filters: dict) -> dict:
    today = date.today()
    rows = await db.contracts.find({}, {"_id": 0}).to_list(5000)
    for r in rows:
        await _recompute_contract_status(r)
    rows = [r for r in rows if r.get("status") == "overdue"]
    rows = await _enrich_contracts_with_item_meta(rows)
    rows = _apply_date_filter(rows, "due_date", filters.get("month"), filters.get("year"))
    rows = _apply_item_filter(rows, filters.get("category"), filters.get("sub_category"))
    total_overdue = len(rows)
    total_outstanding = sum(float(r.get("principal_remaining", 0) or 0) for r in rows)
    total_interest = sum(float(r.get("interest_remaining", 0) or 0) for r in rows)
    near = today + timedelta(days=7)
    near_expired = sum(
        1 for r in rows
        if r.get("due_date") and r["due_date"] >= today.isoformat() and r["due_date"] <= near.isoformat()
    )
    return {
        "kpis": {
            "total_overdue": total_overdue,
            "total_outstanding": round(total_outstanding, 2),
            "total_interest": round(total_interest, 2),
            "near_expired": near_expired,
        },
        "columns": ["contract_number", "item_type", "item_brand", "item_model", "loan_amount",
                    "principal_remaining", "interest_remaining", "penalty", "due_date", "status"],
        "rows": rows,
    }


async def _report_auction(filters: dict) -> dict:
    rows = await db.auctions.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    rows = _apply_date_filter(rows, "created_at", filters.get("month"), filters.get("year"))
    rows = _apply_item_filter(rows, filters.get("category"), filters.get("sub_category"))
    total_auction = len(rows)
    total_amount = sum(float(r.get("sold_price") or r.get("starting_price") or 0) for r in rows)
    return {
        "kpis": {
            "total_auction": total_auction,
            "total_amount": round(total_amount, 2),
        },
        "columns": ["contract_number", "item_type", "starting_price", "sold_price",
                    "buyer_name", "status", "sold_at"],
        "rows": rows,
    }


async def _report_inventory(filters: dict) -> dict:
    out_rows: list[dict] = []
    for kind, coll in COLLECTION_MAP.items():
        items = await db[coll].find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
        for it in items:
            out_rows.append({
                "kind": kind,
                "id": it["id"],
                "brand": it.get("brand", ""),
                "model": it.get("model", ""),
                "category": it.get("category", ""),
                "location": it.get("location", ""),
                "manufacture_year": it.get("manufacture_year"),
                "market_value": float(it.get("market_value", 0) or 0),
                "status": it.get("status", "in_stock"),
                "created_at": it.get("created_at", ""),
            })
    if filters.get("category"):
        out_rows = [r for r in out_rows if r["kind"] == filters["category"]]
    if filters.get("sub_category"):
        out_rows = [r for r in out_rows if r.get("category") == filters["sub_category"]]
    out_rows = _apply_date_filter(out_rows, "created_at", filters.get("month"), filters.get("year"))

    total_items = len(out_rows)
    total_amount = sum(float(r["market_value"]) for r in out_rows)
    active_items = sum(1 for r in out_rows if r["status"] in ("pawned", "in_stock"))
    overdue_items = 0
    # count overdue by looking up active contracts whose status is overdue
    overdue_contracts = await db.contracts.find({"status": "overdue"}, {"_id": 0}).to_list(5000)
    overdue_item_ids = {c["item_id"] for c in overdue_contracts}
    overdue_items = sum(1 for r in out_rows if r["id"] in overdue_item_ids)

    by_type = {
        "car": sum(1 for r in out_rows if r["kind"] == "car"),
        "motorcycle": sum(1 for r in out_rows if r["kind"] == "motorcycle"),
        "electronic": sum(1 for r in out_rows if r["kind"] == "electronic"),
    }
    return {
        "kpis": {
            "total_items": total_items,
            "total_amount": round(total_amount, 2),
            "active_items": active_items,
            "overdue_items": overdue_items,
            "by_type": by_type,
        },
        "columns": ["kind", "brand", "model", "category", "location",
                    "manufacture_year", "market_value", "status", "created_at"],
        "rows": out_rows,
    }


async def _report_financial(filters: dict) -> dict:
    contracts = await db.contracts.find({}, {"_id": 0}).to_list(5000)
    for c in contracts:
        await _recompute_contract_status(c)
    contracts = await _enrich_contracts_with_item_meta(contracts)
    contracts_filtered = _apply_date_filter(contracts, "contract_date", filters.get("month"), filters.get("year"))
    contracts_filtered = _apply_item_filter(contracts_filtered, filters.get("category"), filters.get("sub_category"))

    payments = await db.payments.find({}, {"_id": 0}).to_list(5000)
    payments = await _enrich_payments_with_contract(payments)
    payments_filtered = _apply_date_filter(payments, "date", filters.get("month"), filters.get("year"))
    payments_filtered = _apply_item_filter(payments_filtered, filters.get("category"), filters.get("sub_category"))

    total_loan = sum(float(c.get("loan_amount", 0) or 0) for c in contracts_filtered)
    total_payment = sum(float(p.get("amount", 0) or 0) for p in payments_filtered)
    interest_received = sum(float(c.get("interest_paid", 0) or 0) for c in contracts_filtered)
    total_penalty = sum(float(c.get("penalty", 0) or 0) for c in contracts_filtered)
    profit = round(interest_received + total_penalty, 2)

    # Table rows: 1 line summary per contract
    rows = [
        {
            "contract_number": c.get("contract_number"),
            "loan_amount": float(c.get("loan_amount", 0) or 0),
            "paid_amount": float(c.get("paid_amount", 0) or 0),
            "interest_received": float(c.get("interest_paid", 0) or 0),
            "penalty": float(c.get("penalty", 0) or 0),
            "profit": round(float(c.get("interest_paid", 0) or 0) + float(c.get("penalty", 0) or 0), 2),
            "status": c.get("status"),
            "contract_date": c.get("contract_date"),
        }
        for c in contracts_filtered
    ]
    return {
        "kpis": {
            "total_loan": round(total_loan, 2),
            "total_payment": round(total_payment, 2),
            "interest_received": round(interest_received, 2),
            "profit": profit,
            "total_penalty": round(total_penalty, 2),
        },
        "columns": ["contract_number", "contract_date", "loan_amount", "paid_amount",
                    "interest_received", "penalty", "profit", "status"],
        "rows": rows,
    }


REPORT_BUILDERS = {
    "active-contracts": _report_active_contracts,
    "payments": _report_payments,
    "overdue": _report_overdue,
    "auction": _report_auction,
    "inventory": _report_inventory,
    "financial": _report_financial,
}


@api.get("/reports/v2/{report_type}")
async def reports_v2(
    report_type: str,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    category: Optional[str] = Query(None),
    sub_category: Optional[str] = Query(None),
    _: dict = Depends(get_current_user),
):
    builder = REPORT_BUILDERS.get(report_type)
    if not builder:
        raise HTTPException(status_code=400, detail="Unknown report type")
    return await builder({
        "month": month, "year": year,
        "category": category, "sub_category": sub_category,
    })


@api.get("/reports/v2/{report_type}/export")
async def reports_export(
    report_type: str,
    format: str = Query("xlsx", regex="^(xlsx|csv|pdf)$"),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    category: Optional[str] = Query(None),
    sub_category: Optional[str] = Query(None),
    _: dict = Depends(get_current_user),
):
    builder = REPORT_BUILDERS.get(report_type)
    if not builder:
        raise HTTPException(status_code=400, detail="Unknown report type")
    data = await builder({
        "month": month, "year": year,
        "category": category, "sub_category": sub_category,
    })
    rows = data["rows"]
    columns = data["columns"]
    name = f"{report_type}-{date.today().isoformat()}"

    if format == "csv":
        import io
        import csv
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in columns})
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
        )

    if format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = Workbook()
        ws = wb.active
        ws.title = report_type[:30]
        # KPI header
        ws.append(["Fatin Penhores — " + report_type.replace("-", " ").title()])
        ws["A1"].font = Font(bold=True, size=14, color="2F4F4F")
        ws.append([])
        # KPI cards as label/value pairs
        kpi_row = 3
        for k, v in data["kpis"].items():
            if isinstance(v, dict):
                continue
            ws.cell(row=kpi_row, column=1, value=k.replace("_", " ").title()).font = Font(bold=True)
            ws.cell(row=kpi_row, column=2, value=v)
            kpi_row += 1
        ws.append([])
        header_row = kpi_row + 1
        for i, col in enumerate(columns, start=1):
            c = ws.cell(row=header_row, column=i, value=col.replace("_", " ").title())
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="2F4F4F")
            c.alignment = Alignment(horizontal="center")
        for r in rows:
            ws.append([r.get(c, "") for c in columns])
        # auto column widths
        for col_cells in ws.columns:
            max_len = 8
            col_letter = col_cells[0].column_letter
            for cell in col_cells:
                v = cell.value
                if v is None:
                    continue
                ln = len(str(v))
                if ln > max_len:
                    max_len = ln
            ws.column_dimensions[col_letter].width = min(max_len + 2, 40)
        buf = BytesIO()
        wb.save(buf)
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
        )

    # PDF
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table as RLTable, TableStyle, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm

    base = getSampleStyleSheet()
    title_style = ParagraphStyle("rT", parent=base["Title"], fontSize=15, textColor=colors.HexColor("#2F4F4F"))
    sub_style = ParagraphStyle("rS", parent=base["Normal"], fontSize=9, textColor=colors.HexColor("#57534E"))

    buf = BytesIO()
    pdf_doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.2*cm, rightMargin=1.2*cm, topMargin=1*cm, bottomMargin=1*cm)
    story = [
        Paragraph(f"Fatin Penhores — {report_type.replace('-', ' ').title()}", title_style),
        Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC", sub_style),
        Spacer(1, 0.4*cm),
    ]
    # KPI table
    kpi_pairs = [(k.replace("_", " ").title(), str(v)) for k, v in data["kpis"].items() if not isinstance(v, dict)]
    if kpi_pairs:
        kpi_tbl = RLTable([list(pair) for pair in kpi_pairs], colWidths=[5*cm, 5*cm])
        kpi_tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F5F4")),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6D3D1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E7E5E4")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(kpi_tbl)
        story.append(Spacer(1, 0.4*cm))
    # Data table
    table_data = [[c.replace("_", " ").title() for c in columns]]
    for r in rows[:300]:
        table_data.append([str(r.get(c, "") or "") for c in columns])
    if len(table_data) > 1:
        rl_t = RLTable(table_data, repeatRows=1)
        rl_t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F4F4F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("LINEBELOW", (0, 1), (-1, -1), 0.2, colors.HexColor("#E7E5E4")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAF9")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(rl_t)
    pdf_doc.build(story)
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
    )


@api.get("/reports/{report_type}")
async def reports(report_type: str, _: dict = Depends(get_current_user)):
    if report_type == "loans":
        items = await db.contracts.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
        return items
    if report_type == "payments":
        items = await db.payments.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
        return items
    if report_type == "profit":
        contracts = await db.contracts.find({}, {"_id": 0}).to_list(5000)
        payments = await db.payments.find({}, {"_id": 0}).to_list(5000)
        paid_by_contract: dict = {}
        for p in payments:
            paid_by_contract[p["contract_id"]] = paid_by_contract.get(p["contract_id"], 0.0) + float(p["amount"])
        rows = []
        for c in contracts:
            loan = float(c.get("loan_amount", 0))
            rate = float(c.get("interest_rate", 0))
            paid = paid_by_contract.get(c["id"], 0.0)
            rows.append({
                "contract_number": c.get("contract_number"),
                "loan_amount": loan,
                "interest_rate": rate,
                "interest_expected": round(loan * rate / 100, 2),
                "paid": round(paid, 2),
                "profit": round(paid - loan, 2) if c.get("status") == "redeemed" else 0,
                "status": c.get("status"),
            })
        return rows
    if report_type == "overdue":
        today = _today_iso()
        items = await db.contracts.find(
            {"due_date": {"$lt": today}, "status": {"$nin": ["redeemed", "auction", "sold"]}},
            {"_id": 0},
        ).to_list(5000)
        return items
    if report_type == "clients":
        return await db.clients.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    if report_type == "contracts":
        return await db.contracts.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    raise HTTPException(status_code=400, detail="Unknown report type")


# =====================================================================
# Public endpoints
# =====================================================================
@api.get("/public/auction-items")
async def public_auction_items():
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
            "description": item.get("description", ""),
            "photo_url": item.get("photo_url", ""),
            "manufacture_year": item.get("manufacture_year"),
            "category": item.get("category"),
        })
    return out


@api.get("/public/warehouse")
async def public_warehouse():
    """Items currently held (pawned but still in stock) — shown to public as inventory teaser."""
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


class ContactIn(BaseModel):
    name: str
    email: EmailStr
    phone: str = ""
    message: str


@api.post("/public/contact")
async def public_contact(payload: ContactIn):
    doc = payload.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.contact_messages.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "id": doc["id"]}


@api.get("/contact-messages")
async def contact_messages(_: dict = Depends(require_admin)):
    return await db.contact_messages.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


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
    by_type = {"car": 0, "motorcycle": 0, "electronic": 0}
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


# =====================================================================
# WhatsApp reminders
# =====================================================================
class WhatsAppSendIn(BaseModel):
    contract_id: str
    language: Literal["en", "tet"] = "en"
    extra: Optional[str] = None


def _wa_template_name(settings: dict, language: str) -> str:
    key = "whatsapp_template_en" if language == "en" else "whatsapp_template_tet"
    return settings.get(key) or settings.get("whatsapp_template_en") or "due_date_reminder"


def _wa_lang_code(language: str) -> str:
    return "en" if language == "en" else "pt_PT"


async def _send_reminder_for_contract(contract: dict, language: str, settings: dict, actor: dict) -> dict:
    client_doc = await db.clients.find_one({"id": contract["client_id"]}, {"_id": 0}) or {}
    phone = client_doc.get("phone", "")
    name = client_doc.get("full_name", "Client")
    cnum = contract.get("contract_number", "")
    due = contract.get("due_date", "")
    remaining = float(contract.get("remaining_balance", 0) or 0)
    params = [name, cnum, due, f"USD {remaining:,.2f}"]
    template = _wa_template_name(settings, language)
    lang_code = _wa_lang_code(language)
    result = await wapp.send_template(phone, template, lang_code, params, settings)
    await db.whatsapp_log.insert_one({
        "id": new_id(),
        "contract_id": contract["id"],
        "contract_number": cnum,
        "client_id": client_doc.get("id"),
        "client_phone": phone,
        "language": language,
        "template": template,
        "parameters": params,
        "result": result,
        "actor_id": actor.get("id"),
        "created_at": utcnow_iso(),
    })
    return result


@api.post("/whatsapp/send")
async def whatsapp_send(payload: WhatsAppSendIn, user: dict = Depends(get_current_user)):
    c = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    c = await _recompute_contract_status(c)
    settings = await get_settings_doc()
    result = await _send_reminder_for_contract(c, payload.language, settings, user)
    await write_audit(user, "whatsapp_send", "contract", c["id"], {"result_status": result.get("status")})
    return result


@api.post("/whatsapp/reminders/run")
async def whatsapp_reminders_run(language: str = Query("en"), user: dict = Depends(require_not_cashier)):
    """Send reminders to all contracts due in N days or overdue (not yet redeemed/auctioned)."""
    settings = await get_settings_doc()
    days_before = int(settings.get("reminder_days_before", 3))
    today = date.today()
    target_due = (today + timedelta(days=days_before)).isoformat()
    today_iso = today.isoformat()
    contracts = await db.contracts.find(
        {"status": {"$in": ["active", "overdue"]}},
        {"_id": 0},
    ).to_list(5000)
    sent: list[dict] = []
    for c in contracts:
        c = await _recompute_contract_status(c)
        due = c.get("due_date", "")
        if due <= target_due or due < today_iso:
            r = await _send_reminder_for_contract(c, language, settings, user)
            sent.append({"contract_number": c.get("contract_number"), "result": r.get("status")})
    return {"count": len(sent), "sent": sent}


@api.get("/whatsapp/logs")
async def whatsapp_logs(_: dict = Depends(get_current_user)):
    return await db.whatsapp_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


# =====================================================================
# Audit log
# =====================================================================
@api.get("/audit-log")
async def audit_log_list(
    limit: int = Query(200, ge=1, le=1000),
    resource: Optional[str] = None,
    _: dict = Depends(require_admin),
):
    q = {"resource": resource} if resource else {}
    return await db.audit_log.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


# =====================================================================
# Health
# =====================================================================
@api.get("/")
async def root():
    return {"service": "Fatin Penhores Pawn System", "status": "ok"}


app.include_router(api)

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
    await db.files.create_index("id", unique=True)
    await db.files.create_index("storage_path")
    for coll in COLLECTION_MAP.values():
        await db[coll].create_index("id", unique=True)

    # Initialize object storage (best-effort)
    try:
        objstore.init_storage()
    except Exception as e:
        logger.warning(f"Object storage not initialized: {e}")

    # Seed settings
    await get_settings_doc()

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@fatinpenhores.tl").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": new_id(),
            "email": admin_email,
            "name": "Administrator",
            "role": "admin",
            "password_hash": hash_password(admin_password),
            "created_at": utcnow_iso(),
        })
        logger.info(f"Seeded admin: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )
        logger.info(f"Updated admin password for: {admin_email}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
