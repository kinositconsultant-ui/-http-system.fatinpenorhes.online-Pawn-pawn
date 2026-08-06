"""Contracts router — CRUD, PDFs, reactivation, bulk email.

Extracted from server.py during the Phase-3 refactor (iter 76). Every path,
method, response shape, and audit trail is preserved — this is a pure move,
no behaviour change.
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
)
from pdf_utils import (
    build_contract_pdf,
    build_loan_terms_card_pdf,
)
import storage as objstore
from realtime import notify as rt_notify

router = APIRouter(tags=["contracts"])


# =====================================================================
# Models
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


class ReactivateIn(BaseModel):
    new_due_date: str  # YYYY-MM-DD
    notes: str = ""


class SignedAgreementIn(BaseModel):
    signed_auction_agreement_url: str
    signed_auction_agreement_thumbnail: str = ""


# =====================================================================
# Helpers
# =====================================================================
async def _generate_contract_number() -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"CTR-{year}-"
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


def _resolve_photo_bytes(photo_url: str) -> bytes | None:
    """Fetch bytes for an image referenced by a stored `photo_url`.

    Handles both external http(s) URLs (redirect avoidance — return None so
    the label falls back gracefully) and internal object-store keys
    (`/files/…`, `/api/files/…`). Returns None on any failure.
    """
    if not photo_url:
        return None
    photo = str(photo_url).strip()
    if photo.lower().startswith(("http://", "https://")):
        try:
            import urllib.request  # noqa: PLC0415
            with urllib.request.urlopen(photo, timeout=3) as resp:
                return resp.read(2_000_000)  # cap at 2 MB
        except Exception:
            return None
    storage_key = photo
    for prefix in ("/api/files/", "/files/", "/api/"):
        if storage_key.startswith(prefix):
            storage_key = storage_key[len(prefix):]
            break
    storage_key = storage_key.lstrip("/")
    try:
        data, _ct = objstore.get_object(storage_key)
        return data
    except Exception:
        return None


# =====================================================================
# Endpoints
# =====================================================================
@router.get("/contracts")
async def list_contracts(_: dict = Depends(require_module("contracts"))):
    contracts = await db.contracts.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    by_kind: dict[str, set[str]] = {}
    for c in contracts:
        kind, iid = c.get("item_type"), c.get("item_id")
        if kind and iid:
            by_kind.setdefault(kind, set()).add(iid)
    photo_map: dict[tuple[str, str], bool] = {}
    for kind, ids in by_kind.items():
        coll = COLLECTION_MAP.get(kind)
        if not coll:
            continue
        docs = await db[coll].find(
            {"id": {"$in": list(ids)}},
            {"_id": 0, "id": 1, "photo_url": 1},
        ).to_list(len(ids))
        for d in docs:
            photo_map[(kind, d["id"])] = bool((d.get("photo_url") or "").strip())
    out = []
    for c in contracts:
        c = await _recompute_contract_status(c)
        c["has_item_photo"] = photo_map.get(
            (c.get("item_type"), c.get("item_id")), False
        )
        out.append(c)
    return out


@router.post("/contracts")
async def create_contract(payload: ContractIn, user: dict = Depends(require_not_cashier)):
    # Deferred import — payments router owns receipt-number generation
    from routes.payments import _generate_receipt_number  # noqa: PLC0415

    client_doc = await db.clients.find_one({"id": payload.client_id}, {"_id": 0})
    if not client_doc:
        raise HTTPException(status_code=404, detail="Client not found")
    item = await _fetch_item(payload.item_type, payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.get("status") not in ("in_stock", None):
        raise HTTPException(status_code=400, detail="Item is not available")
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
    if not doc.get("interest_rate"):
        sett = await get_settings_doc()
        defaults = {
            "car": sett.get("interest_rate_car", 10),
            "motorcycle": sett.get("interest_rate_motorcycle", 10),
            "electronic": sett.get("interest_rate_electronic", 15),
            "pezadu": sett.get("interest_rate_pezadu", 10),
        }
        doc["interest_rate"] = defaults[payload.item_type]
    doc["id"] = new_id()
    doc["contract_number"] = contract_number
    doc["status"] = "active"
    doc["interest_rule"] = "M1"
    doc["created_at"] = utcnow_iso()
    await db.contracts.insert_one(doc)
    await db[COLLECTION_MAP[payload.item_type]].update_one(
        {"id": payload.item_id},
        {"$set": {"status": "pawned", "active_contract_id": doc["id"]}},
    )
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
    rt_notify("contract.created", {"contract_id": doc["id"], "contract_number": contract_number})
    return await _recompute_contract_status(doc)


@router.post("/contracts/{cid}/reactivate")
async def reactivate_contract(cid: str, payload: ReactivateIn, user: dict = Depends(require_not_cashier)):
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    c = await _recompute_contract_status(c)
    if c["status"] not in ("overdue", "grace_period", "active", "auction_ready"):
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


@router.get("/contracts/labels-pdf")
async def contracts_bulk_labels_pdf(
    ids: str = "",
    month: str = "",
    status: str = "",
    layout: str = "single",
    _: dict = Depends(get_current_user),
):
    """Batch printable-label PDF — one A6 page per contract."""
    from pdf_utils import build_bulk_labels_pdf  # noqa: PLC0415

    q: dict = {}
    id_list = [s for s in (ids or "").split(",") if s.strip()]
    if id_list:
        q["id"] = {"$in": id_list[:500]}
    if month:
        q["contract_date"] = {"$regex": f"^{month}"}
    if status:
        q["status"] = status
    if not q:
        q["status"] = {"$in": ["active", "grace_period", "overdue", "auction_ready"]}

    contracts = await db.contracts.find(q, {"_id": 0}).sort("contract_number", 1).to_list(500)
    if not contracts:
        pdf_bytes = build_bulk_labels_pdf([], layout=layout)
    else:
        client_ids = list({c["client_id"] for c in contracts if c.get("client_id")})
        client_docs = {
            d["id"]: d
            for d in await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0}).to_list(500)
        } if client_ids else {}
        rows: list[tuple] = []
        for c in contracts:
            item = await _fetch_item(c.get("item_type"), c.get("item_id")) or {}
            client_doc = client_docs.get(c.get("client_id"))
            photo = _resolve_photo_bytes(item.get("photo_url", "")) if item else None
            rows.append((c, item, client_doc, photo))
        pdf_bytes = build_bulk_labels_pdf(rows, layout=layout)

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="fatin-penhores-labels-{month or "batch"}.pdf"'},
    )


@router.get("/contracts/{cid}")
async def get_contract(cid: str, _: dict = Depends(get_current_user)):
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    return await _recompute_contract_status(c)


@router.delete("/contracts/{cid}")
async def delete_contract(cid: str, _: dict = Depends(require_admin)):
    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    await db.payments.delete_many({"contract_id": cid})
    await db.contracts.delete_one({"id": cid})
    await db[COLLECTION_MAP[c["item_type"]]].update_one(
        {"id": c["item_id"]},
        {"$set": {"status": "in_stock"}, "$unset": {"active_contract_id": ""}},
    )
    return {"ok": True}


@router.get("/contracts/{cid}/pdf")
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


@router.get("/contracts/{cid}/label-pdf")
async def contract_label_pdf(cid: str, _: dict = Depends(get_current_user)):
    """Printable QR sticker label for the physical pawned item."""
    from pdf_utils import build_item_label_pdf  # noqa: PLC0415

    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    item = await _fetch_item(c.get("item_type"), c.get("item_id")) or {}
    client_doc = await db.clients.find_one({"id": c.get("client_id")}, {"_id": 0}) or {}
    photo_bytes = _resolve_photo_bytes(item.get("photo_url", "")) if item else None
    pdf_bytes = build_item_label_pdf(c, item, client_doc, item_photo_bytes=photo_bytes)
    safe_no = str(c.get("contract_number", "label")).replace("/", "-")
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_no}-label.pdf"'},
    )


@router.post("/contracts/{cid}/signed-auction-agreement")
async def contract_signed_auction_agreement(
    cid: str,
    payload: SignedAgreementIn,
    user: dict = Depends(require_not_cashier),
):
    """Attach a scan/photo of the signed auction agreement to the contract."""
    res = await db.contracts.update_one(
        {"id": cid},
        {"$set": {
            "signed_auction_agreement_url": payload.signed_auction_agreement_url,
            "signed_auction_agreement_thumbnail": payload.signed_auction_agreement_thumbnail,
            "signed_auction_agreement_at": utcnow_iso(),
            "signed_auction_agreement_by": user.get("id"),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contract not found")
    await write_audit(
        user, "attach_signed_agreement", "contract", cid,
        {"url": payload.signed_auction_agreement_url},
    )
    return await db.contracts.find_one({"id": cid}, {"_id": 0})


@router.get("/contracts/{cid}/auction-agreement-pdf")
async def contract_auction_agreement_pdf(cid: str, _: dict = Depends(get_current_user)):
    """Formal auction agreement between the client and the company."""
    from pdf_utils import build_auction_agreement_pdf  # noqa: PLC0415

    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    client_doc = await db.clients.find_one({"id": c.get("client_id")}, {"_id": 0}) or {}
    item = await _fetch_item(c.get("item_type"), c.get("item_id")) or {}
    settings = await get_settings_doc()
    pdf_bytes = build_auction_agreement_pdf(c, client_doc, item, settings=settings)
    safe_no = str(c.get("contract_number", "auction")).replace("/", "-")
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_no}-auction-agreement.pdf"'},
    )


@router.get("/contracts/{cid}/terms-card")
async def contract_terms_card(cid: str, _: dict = Depends(get_current_user)):
    """Personalized "Terms of your Loan" one-pager."""
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


@router.post("/contracts/bulk-email-history")
async def contracts_bulk_email_history(
    status: str = "grace_period,auction_ready",
    user: dict = Depends(get_current_user),
):
    """Bulk email payment-history PDFs to every client with a matching contract."""
    from pdf_utils import build_payment_history_pdf  # noqa: PLC0415
    import email_svc  # noqa: PLC0415

    statuses = [s.strip() for s in status.split(",") if s.strip()]
    if not statuses:
        statuses = ["grace_period", "auction_ready"]

    contracts = await db.contracts.find(
        {"status": {"$in": statuses}}, {"_id": 0}
    ).to_list(500)
    if not contracts:
        return {"total": 0, "sent": 0, "skipped_no_email": 0, "failed": 0}

    seen_clients: set[str] = set()
    to_send: list[dict] = []
    for c in contracts:
        cid = c.get("client_id")
        if not cid or cid in seen_clients:
            continue
        seen_clients.add(cid)
        to_send.append(c)

    client_ids = list(seen_clients)
    client_docs = {
        d["id"]: d
        for d in await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0}).to_list(500)
    }

    sent = failed = skipped = 0
    for c in to_send:
        client_doc = client_docs.get(c.get("client_id")) or {}
        email = (client_doc.get("email") or "").strip()
        if not email:
            skipped += 1
            continue
        try:
            c_full = await _recompute_contract_status(c)
            item = await _fetch_item(c_full.get("item_type"), c_full.get("item_id")) or {}
            payments = await db.payments.find(
                {"contract_id": c_full["id"]}, {"_id": 0}
            ).to_list(500)
            pdf_bytes = build_payment_history_pdf(c_full, client_doc, item, payments)
            first_name = (client_doc.get("full_name") or "Client").split(" ")[0]
            subject = f"{email_svc.BRAND} — Overdue Reminder · {c_full.get('contract_number','')}"
            html = f"""
<!doctype html><html><body style='font-family: Arial, sans-serif; color:#0F1B3A;'>
  <p>Hi {first_name},</p>
  <p>Your contract <b>{c_full.get('contract_number','')}</b> is currently past due.
     Please find the full payment history attached and let us know if you'd like
     to pay or extend.</p>
  <p>WhatsApp: +670 78372678</p>
  {email_svc.FOOTER_HTML}
</body></html>"""
            safe_no = str(c_full.get("contract_number", "history")).replace("/", "-")
            r = await email_svc.send_email(
                email, subject, html,
                attachments=[{"filename": f"{safe_no}-history.pdf", "content": pdf_bytes}],
            )
            if r.get("status") in ("sent", "mocked"):
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    await write_audit(user, "bulk_email_history", "contract", "-", {
        "total": len(to_send), "sent": sent, "skipped": skipped, "failed": failed,
    })
    return {"total": len(to_send), "sent": sent, "skipped_no_email": skipped, "failed": failed}


@router.post("/contracts/{cid}/email-history")
async def contract_email_history(cid: str, user: dict = Depends(get_current_user)):
    """Email the payment-history summary PDF to the contract's client."""
    from pdf_utils import build_payment_history_pdf  # noqa: PLC0415
    import email_svc  # noqa: PLC0415

    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    c = await _recompute_contract_status(c)
    client_doc = await db.clients.find_one({"id": c.get("client_id")}, {"_id": 0}) or {}
    to_email = (client_doc.get("email") or "").strip()
    if not to_email:
        raise HTTPException(status_code=400, detail="Client has no email on file")
    item = await _fetch_item(c.get("item_type"), c.get("item_id")) or {}
    payments = await db.payments.find({"contract_id": cid}, {"_id": 0}).to_list(500)
    pdf_bytes = build_payment_history_pdf(c, client_doc, item, payments)
    subject = f"{email_svc.BRAND} — Payment History {c.get('contract_number','')}"
    html = f"""
<!doctype html><html><body style='font-family: Arial, sans-serif; color:#0F1B3A;'>
  <p>Hi {(client_doc.get('full_name') or 'Client').split(' ')[0]},</p>
  <p>Attached is the full payment history for your contract
     <b>{c.get('contract_number','')}</b>.
     Individual receipt PDFs remain available on request.</p>
  <p>Questions? Reply to this email or WhatsApp us at +670 78372678.</p>
  {email_svc.FOOTER_HTML}
</body></html>"""
    safe_no = str(c.get("contract_number", "history")).replace("/", "-")
    result = await email_svc.send_email(
        to_email,
        subject,
        html,
        attachments=[{"filename": f"{safe_no}-payment-history.pdf", "content": pdf_bytes}],
    )
    await write_audit(user, "email_payment_history", "contract", cid, {"to": to_email, "status": result.get("status")})
    return {"ok": True, "email_status": result.get("status"), "to": to_email, "note": result.get("note")}


@router.get("/contracts/{cid}/payments-summary-pdf")
async def contract_payments_summary_pdf(cid: str, _: dict = Depends(get_current_user)):
    """Combined payment-history summary PDF for a single contract."""
    from pdf_utils import build_payment_history_pdf  # noqa: PLC0415

    c = await db.contracts.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    c = await _recompute_contract_status(c)
    client_doc = await db.clients.find_one({"id": c.get("client_id")}, {"_id": 0}) or {}
    item = await _fetch_item(c.get("item_type"), c.get("item_id")) or {}
    payments = await db.payments.find({"contract_id": cid}, {"_id": 0}).to_list(500)
    pdf_bytes = build_payment_history_pdf(c, client_doc, item, payments)
    safe_no = str(c.get("contract_number", "history")).replace("/", "-")
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_no}-payment-history.pdf"'},
    )
