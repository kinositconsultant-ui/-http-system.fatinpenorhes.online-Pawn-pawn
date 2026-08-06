"""Auctions + Invoices router — auction lifecycle, invoice CRUD, catalogue PDF.

Extracted from server.py during the Phase-3 refactor (iter 76). Preserves the
in-process catalogue-PDF cache (`_CATALOGUE_CACHE` + `get_or_build_catalogue_pdf`)
that `routes/public.py` and `scheduler.py` import.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deps import (
    db,
    new_id,
    utcnow_iso,
    COLLECTION_MAP,
    get_current_user,
    require_admin,
    require_module,
    require_not_cashier,
    write_audit,
)
from services import (
    _fetch_item,
    _recompute_contract_status,
    get_settings_doc,
    _today_iso,
)
from pdf_utils import (
    build_invoice_pdf,
    build_invoices_list_pdf,
)
from realtime import notify as rt_notify

router = APIRouter(tags=["auctions"])


# =====================================================================
# Models
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


class InvoiceUpdateIn(BaseModel):
    buyer_name: Optional[str] = None
    buyer_phone: Optional[str] = None
    buyer_email: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_id_number: Optional[str] = None
    tax_percent: Optional[float] = None
    status: Optional[Literal["issued", "paid", "cancelled"]] = None
    notes: Optional[str] = None


# =====================================================================
# Helpers
# =====================================================================
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


# In-process cache for the auction catalogue PDF. Preserved from server.py so
# scheduler.py and routes/public.py can continue to import it verbatim.
_CATALOGUE_CACHE: dict = {"bytes": None, "generated_at": None, "next_date": None, "item_count": 0}


async def _build_catalogue_bytes_now() -> tuple[bytes, dict]:
    """Fetch fresh data, build the PDF, and update the in-process cache."""
    from pdf_utils import build_auction_catalogue_pdf  # noqa: PLC0415

    contracts = await db.contracts.find(
        {"status": {"$in": ["auction_ready", "auction"]}}, {"_id": 0}
    ).to_list(5000)
    contracts.sort(key=lambda c: c.get("contract_number", ""))
    rows: list[dict] = []
    for c in contracts:
        kind = c.get("item_type")
        coll = COLLECTION_MAP.get(kind)
        item: dict = {}
        if coll and c.get("item_id"):
            item = await db[coll].find_one({"id": c["item_id"]}, {"_id": 0}) or {}
        market = float(item.get("market_value") or c.get("loan_amount") or 0)
        rows.append({
            "reference": c.get("contract_number"),
            "contract_number": c.get("contract_number"),
            "item_type": kind,
            "brand": item.get("brand"),
            "model": item.get("model"),
            "year": item.get("year") or item.get("manufacture_year"),
            "color": item.get("color"),
            "plate": item.get("plate"),
            "description": item.get("description") or item.get("name"),
            "market_value": market,
            "min_bid": round(market * 0.70, 2),
        })
    settings_doc = await get_settings_doc()
    next_date = (settings_doc or {}).get("next_auction_date", "") or ""
    generated_at = _today_iso()
    pdf_bytes = build_auction_catalogue_pdf(rows, generated_at=generated_at, next_auction_date=next_date)
    _CATALOGUE_CACHE.update({
        "bytes": pdf_bytes,
        "generated_at": generated_at,
        "next_date": next_date,
        "item_count": len(rows),
    })
    return pdf_bytes, _CATALOGUE_CACHE


async def get_or_build_catalogue_pdf(force: bool = False) -> bytes:
    """Return cached catalogue bytes if fresh, otherwise rebuild."""
    settings_doc = await get_settings_doc()
    current_next_date = (settings_doc or {}).get("next_auction_date", "") or ""
    if (
        not force
        and _CATALOGUE_CACHE.get("bytes")
        and _CATALOGUE_CACHE.get("generated_at") == _today_iso()
        and _CATALOGUE_CACHE.get("next_date") == current_next_date
    ):
        return _CATALOGUE_CACHE["bytes"]
    pdf_bytes, _ = await _build_catalogue_bytes_now()
    return pdf_bytes


# =====================================================================
# Auction endpoints
# =====================================================================
@router.get("/auctions")
async def list_auctions(_: dict = Depends(require_module("auctions"))):
    items = await db.auctions.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    contract_ids = list({a.get("contract_id") for a in items if a.get("contract_id")})
    contracts = await db.contracts.find(
        {"id": {"$in": contract_ids}}, {"_id": 0, "id": 1, "client_id": 1, "contract_number": 1}
    ).to_list(len(contract_ids) or 1)
    contract_to_client = {c["id"]: c.get("client_id") for c in contracts}
    known_contract_ids = {c["id"] for c in contracts}
    client_ids = list({cid for cid in contract_to_client.values() if cid})
    clients = await db.clients.find(
        {"id": {"$in": client_ids}}, {"_id": 0, "id": 1, "full_name": 1}
    ).to_list(len(client_ids) or 1)
    client_id_to_name = {c["id"]: c.get("full_name", "") for c in clients}
    for a in items:
        cid = contract_to_client.get(a.get("contract_id"))
        a["client_id"] = cid
        name = client_id_to_name.get(cid, "") if cid else ""
        if not name:
            cnum = a.get("contract_number", "")
            if a.get("contract_id") and a["contract_id"] not in known_contract_ids and cnum:
                name = f"Deleted Contract · {cnum}"
            elif not cnum:
                name = "Unknown"
            else:
                name = f"Unlinked · {cnum}"
        a["client_name"] = name
    return items


@router.get("/auctions/public")
async def public_auctions():
    items = await db.auctions.find({"status": "listed"}, {"_id": 0}).sort("created_at", -1).to_list(500)
    out = []
    for a in items:
        item = await _fetch_item(a["item_type"], a["item_id"]) or {}
        out.append({**a, "item": item})
    return out


@router.get("/auctions/catalogue/pdf")
async def auction_catalogue_pdf(_: dict = Depends(require_module("auctions"))):
    """Public-safe catalogue PDF of all items eligible for the next auction."""
    pdf_bytes = await get_or_build_catalogue_pdf()
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="auction-catalogue.pdf"'},
    )


@router.post("/auctions/catalogue/refresh")
async def auction_catalogue_refresh(_: dict = Depends(require_admin)):
    """Force-rebuild the cached auction catalogue PDF."""
    pdf_bytes = await get_or_build_catalogue_pdf(force=True)
    return {
        "ok": True,
        "size_bytes": len(pdf_bytes),
        "generated_at": _CATALOGUE_CACHE.get("generated_at"),
        "next_auction_date": _CATALOGUE_CACHE.get("next_date") or "",
        "item_count": _CATALOGUE_CACHE.get("item_count", 0),
    }


@router.post("/auctions/move")
async def move_to_auction(payload: AuctionMoveIn, _: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": payload.contract_id}, {"_id": 0})
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    contract = await _recompute_contract_status(contract)
    if contract["status"] not in ("overdue", "grace_period", "active", "auction_ready"):
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


@router.post("/auctions/{aid}/sold")
async def mark_sold(aid: str, payload: AuctionSoldIn, user: dict = Depends(require_not_cashier)):
    a = await db.auctions.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    if a.get("status") == "sold" and a.get("invoice_id"):
        existing = await db.invoices.find_one({"id": a["invoice_id"]}, {"_id": 0})
        if existing:
            return {**a, "invoice": existing}

    contract = await db.contracts.find_one({"id": a.get("contract_id")}, {"_id": 0}) or {}
    if contract:
        contract = await _recompute_contract_status(contract)
    if payload.interest_fee is None:
        default_fee = float(contract.get("interest_remaining", 0)) + float(contract.get("penalty", 0))
        interest_fee = round(default_fee, 2)
    else:
        interest_fee = round(float(payload.interest_fee), 2)
    sold_price = float(payload.sold_price)
    interest_fee = min(interest_fee, sold_price)
    cash_portion = round(sold_price - interest_fee, 2)

    original_loan_amount = float(
        contract.get("original_loan_amount") or contract.get("loan_amount") or 0
    )
    capital_recovered = round(min(sold_price, original_loan_amount), 2)
    auction_profit = round(max(0.0, sold_price - original_loan_amount), 2)
    realized_loss = round(max(0.0, original_loan_amount - sold_price), 2)

    update = {
        "status": "sold",
        "sold_price": sold_price,
        "interest_fee": interest_fee,
        "cash_portion": cash_portion,
        "original_loan_amount": round(original_loan_amount, 2),
        "capital_recovered": capital_recovered,
        "auction_profit": auction_profit,
        "realized_loss": realized_loss,
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
    rt_notify("auction.sold", {"auction_id": aid, "sold_price": sold_price})
    return {**a, **update, "invoice_id": invoice["id"], "invoice_number": inv_number, "invoice": invoice}


@router.delete("/auctions/{aid}")
async def delete_auction(aid: str, user: dict = Depends(require_admin)):
    """Admin-only: remove an auction listing."""
    a = await db.auctions.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    res = await db.auctions.delete_one({"id": aid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found")
    if a.get("contract_id"):
        contract = await db.contracts.find_one({"id": a["contract_id"]}, {"_id": 0})
        if contract:
            if contract.get("status") in ("auction", "auction_ready"):
                await db.contracts.update_one(
                    {"id": contract["id"]},
                    {"$set": {"status": "grace_period"}, "$unset": {"auction_id": ""}},
                )
    await write_audit(user, "delete", "auction", aid, {
        "contract_id": a.get("contract_id"),
        "contract_number": a.get("contract_number"),
        "status": a.get("status"),
    })
    return {"ok": True}


# =====================================================================
# Invoice endpoints
# =====================================================================
@router.get("/invoices")
async def list_invoices(_: dict = Depends(get_current_user)):
    return await db.invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)


@router.get("/invoices/export/pdf")
async def invoices_list_pdf(_: dict = Depends(get_current_user)):
    invoices = await db.invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    pdf_bytes = build_invoices_list_pdf(invoices)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="invoices.pdf"'},
    )


@router.get("/invoices/{iid}")
async def get_invoice(iid: str, _: dict = Depends(get_current_user)):
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@router.put("/invoices/{iid}")
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


@router.delete("/invoices/{iid}")
async def delete_invoice(iid: str, admin: dict = Depends(require_admin)):
    """Admin-only invoice deletion."""
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    await db.invoices.delete_one({"id": iid})
    auction_id = inv.get("auction_id")
    if auction_id:
        await db.auctions.update_one(
            {"id": auction_id},
            {"$unset": {"invoice_id": "", "invoice_number": ""}},
        )
    await write_audit(admin, "delete", "invoice", iid, {
        "invoice_number": inv.get("invoice_number"),
        "total": inv.get("total"),
        "buyer_name": inv.get("buyer_name"),
    })
    return {"ok": True}


@router.get("/invoices/{iid}/pdf")
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
