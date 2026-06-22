"""Fatin Penhores Pawn System — FastAPI backend."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone, date
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
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
from pdf_utils import build_contract_pdf, build_receipt_pdf

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


# =====================================================================
# Users (admin manages staff)
# =====================================================================
class UserCreateIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["admin", "staff"] = "staff"


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
    id_type: Literal["BI", "Electoral", "Passport"]
    id_number: str
    phone: str
    address: str = ""
    municipality: str = ""
    posto: str = ""
    suco: str = ""
    aldeia: str = ""
    notes: str = ""


@api.get("/clients")
async def list_clients(_: dict = Depends(get_current_user)):
    items = await db.clients.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@api.post("/clients")
async def create_client(payload: ClientIn, _: dict = Depends(get_current_user)):
    doc = payload.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.clients.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/clients/{cid}")
async def get_client(cid: str, _: dict = Depends(get_current_user)):
    c = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return c


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
    year: Optional[int] = None
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
    year: Optional[int] = None
    photo_url: str = ""
    document_url: str = ""


class ElectronicIn(BaseModel):
    category: str  # phone, laptop, tv, etc.
    brand: str
    model: str
    description: str = ""
    serial: str = ""
    condition: str = ""
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
async def create_item(kind: str, payload: dict, _: dict = Depends(get_current_user)):
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
# Contracts
# =====================================================================
class ContractIn(BaseModel):
    client_id: str
    item_id: str
    item_type: Literal["car", "motorcycle", "electronic"]
    loan_amount: float
    interest_rate: Literal[10, 15]
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
    """Compute live status and remaining balance, then persist if changed."""
    if contract.get("status") in ("redeemed", "auction", "sold"):
        return contract
    payments = await db.payments.find({"contract_id": contract["id"]}, {"_id": 0}).to_list(500)
    paid = sum(float(p["amount"]) for p in payments)
    loan = float(contract["loan_amount"])
    rate = float(contract["interest_rate"])
    interest = loan * rate / 100.0
    total_due = loan + interest
    remaining = max(0.0, total_due - paid)
    status = contract.get("status", "active")
    if remaining <= 0.01:
        status = "redeemed"
    elif contract["due_date"] < _today_iso():
        status = "overdue"
    else:
        status = "active"
    if status != contract.get("status"):
        await db.contracts.update_one({"id": contract["id"]}, {"$set": {"status": status}})
    contract["status"] = status
    contract["paid_amount"] = round(paid, 2)
    contract["remaining_balance"] = round(remaining, 2)
    contract["interest_amount"] = round(interest, 2)
    contract["total_due"] = round(total_due, 2)
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
async def create_contract(payload: ContractIn, _: dict = Depends(get_current_user)):
    client_doc = await db.clients.find_one({"id": payload.client_id}, {"_id": 0})
    if not client_doc:
        raise HTTPException(status_code=404, detail="Client not found")
    item = await _fetch_item(payload.item_type, payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.get("status") not in ("in_stock", None):
        raise HTTPException(status_code=400, detail="Item is not available")
    contract_number = await _generate_contract_number()
    doc = payload.model_dump()
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
    doc.pop("_id", None)
    return await _recompute_contract_status(doc)


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
    client_doc = await db.clients.find_one({"id": c["client_id"]}, {"_id": 0}) or {}
    item = await _fetch_item(c["item_type"], c["item_id"]) or {}
    pdf_bytes = build_contract_pdf(c, client_doc, item)
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
async def create_payment(payload: PaymentIn, _: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
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
            "year": item.get("year"),
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
    for coll in COLLECTION_MAP.values():
        await db[coll].create_index("id", unique=True)

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
