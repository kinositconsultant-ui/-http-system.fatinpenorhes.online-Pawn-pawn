"""Finance router — capital sources, operating expenses, finance summary + PDF exports.

Extracted from server.py during Phase 2 refactor.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deps import (
    db,
    new_id,
    utcnow_iso,
    get_current_user,
    require_admin,
    require_not_cashier,
    require_module,
    write_audit,
)
from services import _recompute_contract_status
from pdf_utils import (
    build_finance_summary_pdf,
    build_capital_sources_pdf,
    build_expenses_pdf,
)
from services import _apply_date_filter

router = APIRouter()

# Grouped expense categories. Kept as an ordered list of (group_label, [items])
# so the dropdown can be rendered with section headers. `EXPENSE_CATEGORIES`
# preserves a flat list of every valid category (used for validation & filters).
EXPENSE_CATEGORY_GROUPS = [
    ("Payroll & Bonus", [
        "Salary",
        "Fo Bónus",
        "Compensation",
    ]),
    ("Utilities & Office", [
        "EDTL token Office",
        "Internet Starlink & Telemor",
        "Pulsa telefone",
        "Utilities",
        "Rent",
    ]),
    ("Armazen (Warehouse)", [
        "EDTL token Armazen",
        "Hola Materiál - Armazen 2",
        "Trasporte - Armazen 2",
        "Selu Badain - Armazen 2",
        "Tabela ATK FP - Armazen 2",
    ]),
    ("Transport & Fuel", [
        "Mina Trasporte",
        "Hadia Trasporte Lelaun No Elektróniku",
        "Travel",
    ]),
    ("Operations", [
        "Broker Trata Dokumentus",
        "Maintenance",
        "Meals",
        "Gastus Jerál",
    ]),
    ("Other", [
        "Other",
    ]),
]

EXPENSE_CATEGORIES = [item for _, items in EXPENSE_CATEGORY_GROUPS for item in items]


class FundingSourceIn(BaseModel):
    name: str
    source_type: Literal["bank", "company", "personal", "partner", "other"] = "bank"
    principal_amount: float
    interest_rate: float = 0.0
    interest_period: Literal["monthly", "yearly", "none"] = "monthly"
    term_months: Optional[int] = None
    start_date: str
    due_date: str = ""
    notes: str = ""


@router.get("/funding-sources")
async def list_funding_sources(_: dict = Depends(get_current_user)):
    rows = await db.funding_sources.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # Compute outstanding from repayments
    for r in rows:
        repaid = await db.funding_repayments.find({"source_id": r["id"]}, {"_id": 0}).to_list(500)
        total_repaid = sum(float(x.get("amount", 0) or 0) for x in repaid)
        r["total_repaid"] = round(total_repaid, 2)
        r["outstanding"] = round(max(0.0, float(r["principal_amount"]) - total_repaid), 2)
    return rows


@router.post("/funding-sources")
async def create_funding_source(payload: FundingSourceIn, user: dict = Depends(require_admin)):
    doc = payload.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.funding_sources.insert_one(doc)
    await write_audit(user, "create", "funding_source", doc["id"], {"name": payload.name, "amount": payload.principal_amount})
    doc.pop("_id", None)
    return {**doc, "total_repaid": 0.0, "outstanding": doc["principal_amount"]}


@router.put("/funding-sources/{sid}")
async def update_funding_source(sid: str, payload: FundingSourceIn, user: dict = Depends(require_admin)):
    res = await db.funding_sources.update_one({"id": sid}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Funding source not found")
    await write_audit(user, "update", "funding_source", sid)
    return await db.funding_sources.find_one({"id": sid}, {"_id": 0})


@router.delete("/funding-sources/{sid}")
async def delete_funding_source(sid: str, _: dict = Depends(require_admin)):
    res = await db.funding_sources.delete_one({"id": sid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Funding source not found")
    await db.funding_repayments.delete_many({"source_id": sid})
    return {"ok": True}


class FundingRepaymentIn(BaseModel):
    source_id: str
    amount: float
    date: str
    notes: str = ""


@router.post("/funding-sources/{sid}/repayments")
async def add_repayment(sid: str, payload: FundingRepaymentIn, user: dict = Depends(require_admin)):
    src = await db.funding_sources.find_one({"id": sid}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Funding source not found")
    doc = payload.model_dump()
    doc["source_id"] = sid
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.funding_repayments.insert_one(doc)
    await write_audit(user, "create", "funding_repayment", doc["id"], {"source_id": sid, "amount": payload.amount})
    doc.pop("_id", None)
    return doc


@router.get("/funding-sources/{sid}/repayments")
async def list_repayments(sid: str, _: dict = Depends(get_current_user)):
    return await db.funding_repayments.find({"source_id": sid}, {"_id": 0}).sort("date", -1).to_list(500)


class ExpenseIn(BaseModel):
    category: str  # one of EXPENSE_CATEGORIES or custom
    amount: float
    date: str
    paid_to: str = ""
    description: str = ""
    payment_method: Literal["cash", "bank", "mobile", "other"] = "cash"
    receipt_url: str = ""


@router.get("/expense-categories")
async def expense_categories(_: dict = Depends(get_current_user)):
    return {
        "groups": [{"label": label, "items": items} for label, items in EXPENSE_CATEGORY_GROUPS],
        "flat": EXPENSE_CATEGORIES,
    }


@router.get("/expenses")
async def list_expenses(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    category: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    rows = await db.expenses.find({}, {"_id": 0}).sort("date", -1).to_list(5000)
    rows = _apply_date_filter(rows, "date", month, year)
    if category:
        rows = [r for r in rows if r.get("category") == category]
    return rows


@router.post("/expenses")
async def create_expense(payload: ExpenseIn, user: dict = Depends(require_not_cashier)):
    doc = payload.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    doc["recorded_by"] = user["id"]
    await db.expenses.insert_one(doc)
    await write_audit(user, "create", "expense", doc["id"], {"category": payload.category, "amount": payload.amount})
    doc.pop("_id", None)
    return doc


@router.put("/expenses/{eid}")
async def update_expense(eid: str, payload: ExpenseIn, user: dict = Depends(require_admin)):
    res = await db.expenses.update_one({"id": eid}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    await write_audit(user, "update", "expense", eid)
    return await db.expenses.find_one({"id": eid}, {"_id": 0})


@router.delete("/expenses/{eid}")
async def delete_expense(eid: str, _: dict = Depends(require_admin)):
    res = await db.expenses.delete_one({"id": eid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"ok": True}


@router.get("/finance/summary")
async def finance_summary(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    _: dict = Depends(require_module("finance")),
):
    # Capital sources
    sources = await db.funding_sources.find({}, {"_id": 0}).to_list(500)
    repayments = await db.funding_repayments.find({}, {"_id": 0}).to_list(5000)
    capital_received = sum(float(s.get("principal_amount", 0) or 0) for s in sources)
    capital_repaid = sum(float(r.get("amount", 0) or 0) for r in repayments)
    capital_outstanding = max(0.0, capital_received - capital_repaid)

    # Pawn flows
    contracts = await db.contracts.find({}, {"_id": 0}).to_list(5000)
    loans_disbursed = sum(float(c.get("loan_amount", 0) or 0) for c in contracts)
    payments = await db.payments.find({}, {"_id": 0}).to_list(5000)
    # client_payments = repayments only (exclude disbursement which is money OUT already counted in loans_disbursed)
    client_payments = sum(float(p.get("amount", 0) or 0) for p in payments if p.get("type") != "disbursement")
    auctions = await db.auctions.find({"status": "sold"}, {"_id": 0}).to_list(5000)
    auction_sales = sum(float(a.get("sold_price", 0) or 0) for a in auctions)
    # Auction interest profit (separated from cash recovery — counted as profit only)
    auction_interest_profit = sum(float(a.get("interest_fee", 0) or 0) for a in auctions)
    # Nov-2026 auction split (falls back to computing from sold_price when
    # legacy auction rows don't have the new fields).
    auction_capital_recovered = 0.0
    auction_realized_profit = 0.0
    auction_realized_loss = 0.0
    for a in auctions:
        sp = float(a.get("sold_price", 0) or 0)
        original = float(a.get("original_loan_amount", 0) or 0)
        if not original:
            # Legacy row — best-effort: fall back to sold_price as capital
            auction_capital_recovered += sp
            continue
        auction_capital_recovered += float(a.get("capital_recovered", min(sp, original)) or 0)
        auction_realized_profit += float(a.get("auction_profit", max(0.0, sp - original)) or 0)
        auction_realized_loss += float(a.get("realized_loss", max(0.0, original - sp)) or 0)
    # Invoice tax collected on sold auctions
    invoices_for_tax = await db.invoices.find({}, {"_id": 0}).to_list(5000)
    auction_tax_collected = sum(float(i.get("tax_amount", 0) or 0) for i in invoices_for_tax)

    # Expenses
    expenses = await db.expenses.find({}, {"_id": 0}).to_list(5000)
    expenses_filtered = _apply_date_filter(expenses, "date", month, year)
    expenses_total = sum(float(e.get("amount", 0) or 0) for e in expenses)
    expenses_period = sum(float(e.get("amount", 0) or 0) for e in expenses_filtered)
    # by category
    by_category: dict[str, float] = {}
    for e in expenses_filtered:
        cat = e.get("category", "Other")
        by_category[cat] = by_category.get(cat, 0.0) + float(e.get("amount", 0) or 0)
    by_category_list = [{"category": k, "amount": round(v, 2)} for k, v in by_category.items()]

    # Inspection expenses (Phase D). Incurred amounts are cash-out; client
    # reimbursements are cash-in. Only affects Cash on Hand — not profit.
    inspections_incurred = 0.0
    inspections_reimbursed = 0.0
    async for ins in db.inspections.find({}, {"_id": 0}):
        inspections_incurred += float(ins.get("amount", 0) or 0)
        inspections_reimbursed += float(ins.get("reimbursed_amount", 0) or 0)

    # Profit & cash on hand (lifetime).
    # Cash on Hand includes the auction tax collected from buyers, and starts
    # from a configurable `opening_cash_balance` (settings) that represents
    # capital the shop already had before the system began tracking cash.
    settings_doc = await db.settings.find_one({}, {"_id": 0}) or {}
    opening_cash = float(settings_doc.get("opening_cash_balance", 0) or 0)
    total_inflows = (
        capital_received + client_payments + auction_sales + auction_tax_collected
        + inspections_reimbursed
    )
    total_outflows = (
        loans_disbursed + expenses_total + capital_repaid + inspections_incurred
    )
    cash_on_hand = opening_cash + total_inflows - total_outflows
    # Gross profit (interest + penalties earned) — approximate
    for c in contracts:
        await _recompute_contract_status(c)
    interest_received = sum(float(c.get("interest_paid", 0) or 0) for c in contracts)
    total_penalty = sum(float(c.get("penalty_paid", 0) or 0) for c in contracts)
    # Nov-2026 spec (user rule Feb-2026): Auction realized profit = the
    # `interest_fee` portion of every sold auction. The rest of `sold_price`
    # is treated as principal recovery (Cash on Hand), NOT profit. This gives
    # a clean split:
    #   sold_price   → Cash on Hand
    #   interest_fee → Net Profit
    # Profit sources — three independent buckets as requested:
    #  1. Interest received (all client interest payments)
    #  2. Penalties received
    #  3. Auction profit = interest earned via auction + any realized surplus
    #                      (sale price over principal+interest) minus realized loss
    auction_profit = (
        auction_interest_profit + auction_realized_profit - auction_realized_loss
    )
    gross_profit = interest_received + total_penalty + auction_profit
    net_profit = gross_profit - expenses_total

    # Invoices
    invoices = await db.invoices.find({}, {"_id": 0}).to_list(5000)
    total_invoices = len(invoices)
    total_invoiced = sum(float(i.get("total", 0) or 0) for i in invoices)

    return {
        "cash_on_hand": round(cash_on_hand, 2),
        "opening_cash_balance": round(opening_cash, 2),
        "total_inflows": round(total_inflows, 2),
        "total_outflows": round(total_outflows, 2),
        "capital_received": round(capital_received, 2),
        "capital_repaid": round(capital_repaid, 2),
        "capital_outstanding": round(capital_outstanding, 2),
        "loans_disbursed": round(loans_disbursed, 2),
        "client_payments": round(client_payments, 2),
        "auction_sales": round(auction_sales, 2),
        "auction_interest_profit": round(auction_interest_profit, 2),
        "auction_capital_recovered": round(auction_capital_recovered, 2),
        "auction_realized_profit": round(auction_realized_profit, 2),
        "auction_realized_loss": round(auction_realized_loss, 2),
        "auction_tax_collected": round(auction_tax_collected, 2),
        "expenses_total": round(expenses_total, 2),
        "expenses_period": round(expenses_period, 2),
        "inspections_incurred": round(inspections_incurred, 2),
        "inspections_reimbursed": round(inspections_reimbursed, 2),
        "inspections_net_cost": round(inspections_incurred - inspections_reimbursed, 2),
        "interest_received": round(interest_received, 2),
        "total_penalty": round(total_penalty, 2),
        "auction_profit": round(auction_profit, 2),
        "gross_profit": round(gross_profit, 2),
        "net_profit": round(net_profit, 2),
        "expenses_by_category": by_category_list,
        "total_invoices": total_invoices,
        "total_invoiced": round(total_invoiced, 2),
    }


# =====================================================================
# Cash-on-Hand ledger (Phase H · iter 64)
# =====================================================================
@router.get("/finance/cash-ledger")
async def cash_ledger(
    days: int = Query(90, ge=1, le=365, description="Last N days of history"),
    _: dict = Depends(get_current_user),
):
    """Synthesize a per-line cash-movement ledger from every cash-affecting
    collection. Nothing is persisted — this is a live projection over the
    existing payments / expenses / inspections / funding data. Signed
    amounts: inflows positive, outflows negative. Running balance is
    computed forward from `opening_cash_balance`."""
    from datetime import date as _date, timedelta as _td
    cutoff = (_date.today() - _td(days=days)).isoformat()
    settings_doc = await db.settings.find_one({}, {"_id": 0}) or {}
    opening_cash = float(settings_doc.get("opening_cash_balance", 0) or 0)

    entries: list[dict] = []

    # 1. Payments: disbursement = outflow, others = inflow
    async for p in db.payments.find({"date": {"$gte": cutoff}}, {"_id": 0}):
        amt = float(p.get("amount", 0) or 0)
        is_out = p.get("type") == "disbursement"
        entries.append({
            "date": p.get("date"),
            "kind": "disbursement" if is_out else "payment",
            "source": "payments",
            "amount": -amt if is_out else amt,
            "reference": p.get("receipt_number") or p.get("id"),
            "notes": f"{p.get('type','')} · contract {p.get('contract_number','')}",
        })

    # 2. Expenses (outflow)
    async for e in db.expenses.find({"date": {"$gte": cutoff}}, {"_id": 0}):
        entries.append({
            "date": e.get("date"),
            "kind": "expense",
            "source": "expenses",
            "amount": -float(e.get("amount", 0) or 0),
            "reference": e.get("id"),
            "notes": f"{e.get('category','')} · {e.get('description','')}",
        })

    # 3. Inspections — incurred (outflow) + reimbursed (inflow, on reimbursed_date)
    async for ins in db.inspections.find({}, {"_id": 0}):
        if (ins.get("incurred_date") or "") >= cutoff:
            entries.append({
                "date": ins.get("incurred_date"),
                "kind": "inspection_out",
                "source": "inspections",
                "amount": -float(ins.get("amount", 0) or 0),
                "reference": ins.get("id"),
                "notes": f"{ins.get('category','')} · {ins.get('description','')} · contract {ins.get('contract_number','')}",
            })
        if ins.get("reimbursed") and (ins.get("reimbursed_date") or "") >= cutoff:
            entries.append({
                "date": ins.get("reimbursed_date"),
                "kind": "inspection_reimb",
                "source": "inspections",
                "amount": float(ins.get("reimbursed_amount", 0) or 0),
                "reference": ins.get("id"),
                "notes": f"reimburse · {ins.get('category','')} · contract {ins.get('contract_number','')}",
            })

    # 4. Funding sources (capital in) + repayments (capital out)
    async for f in db.funding_sources.find({}, {"_id": 0}):
        if (f.get("start_date") or "") >= cutoff:
            entries.append({
                "date": f.get("start_date"),
                "kind": "capital_in",
                "source": "funding_sources",
                "amount": float(f.get("principal_amount", 0) or 0),
                "reference": f.get("id"),
                "notes": f"capital from {f.get('name','')}",
            })
    async for r in db.funding_repayments.find({"date": {"$gte": cutoff}}, {"_id": 0}):
        entries.append({
            "date": r.get("date"),
            "kind": "capital_out",
            "source": "funding_repayments",
            "amount": -float(r.get("amount", 0) or 0),
            "reference": r.get("id"),
            "notes": f"repayment · {r.get('notes','')}",
        })

    # 5. Auctions (inflow when sold_price captured on `date_sold`)
    async for a in db.auctions.find({}, {"_id": 0}):
        if (a.get("date_sold") or "") >= cutoff and a.get("sold_price"):
            entries.append({
                "date": a.get("date_sold"),
                "kind": "auction_sale",
                "source": "auctions",
                "amount": float(a.get("sold_price", 0) or 0),
                "reference": a.get("id"),
                "notes": f"auction · contract {a.get('contract_number','')}",
            })
            if a.get("tax_collected"):
                entries.append({
                    "date": a.get("date_sold"),
                    "kind": "auction_tax",
                    "source": "auctions",
                    "amount": float(a.get("tax_collected", 0) or 0),
                    "reference": a.get("id"),
                    "notes": "buyer tax collected",
                })

    # Sort ascending by date so the running balance flows forward.
    entries.sort(key=lambda e: (e.get("date") or "", e.get("kind") or ""))
    balance = opening_cash
    for e in entries:
        balance += e["amount"]
        e["running_balance"] = round(balance, 2)
        e["amount"] = round(e["amount"], 2)

    total_in = sum(e["amount"] for e in entries if e["amount"] > 0)
    total_out = -sum(e["amount"] for e in entries if e["amount"] < 0)
    # Present newest-first for the UI
    entries.reverse()
    return {
        "opening_cash": round(opening_cash, 2),
        "period_days": days,
        "period_from": cutoff,
        "total_in": round(total_in, 2),
        "total_out": round(total_out, 2),
        "closing_balance": round(balance, 2),
        "entries": entries,
    }


# ---- Upcoming company loan repayments (Phase H · iter 64) ------------
@router.get("/finance/upcoming-repayments")
async def upcoming_repayments(
    days_ahead: int = Query(30, ge=1, le=180),
    _: dict = Depends(get_current_user),
):
    """Funding sources with a due_date within the next N days and unpaid balance.
    Powers the Company Loan reminder panel on the Finance page."""
    from datetime import date as _date, timedelta as _td
    today = _date.today().isoformat()
    horizon = (_date.today() + _td(days=days_ahead)).isoformat()

    sources = await db.funding_sources.find({}, {"_id": 0}).to_list(200)
    upcoming = []
    for s in sources:
        due = s.get("due_date") or ""
        if not due or due > horizon:
            continue
        # Compute outstanding
        repays = await db.funding_repayments.find(
            {"funding_source_id": s.get("id")}, {"_id": 0}
        ).to_list(500)
        repaid = sum(float(r.get("amount", 0) or 0) for r in repays)
        outstanding = max(0.0, float(s.get("principal_amount", 0) or 0) - repaid)
        if outstanding <= 0:
            continue
        try:
            from datetime import date as _d
            days_until = (_d.fromisoformat(due) - _d.fromisoformat(today)).days
        except Exception:
            days_until = None
        upcoming.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "source_type": s.get("source_type"),
            "principal_amount": round(float(s.get("principal_amount", 0) or 0), 2),
            "repaid": round(repaid, 2),
            "outstanding": round(outstanding, 2),
            "due_date": due,
            "days_until_due": days_until,
            "interest_rate": s.get("interest_rate"),
            "interest_period": s.get("interest_period"),
        })
    upcoming.sort(key=lambda x: x["due_date"])
    return {"days_ahead": days_ahead, "count": len(upcoming), "sources": upcoming}



# ---- Finance PDF exports ----------------------------------------------
@router.get("/finance/summary/export/pdf")
async def finance_summary_pdf(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    user: dict = Depends(get_current_user),
):
    summary = await finance_summary(month=month, year=year, _=user)  # type: ignore[arg-type]
    pdf_bytes = build_finance_summary_pdf(summary, month=month, year=year)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="finance-summary.pdf"'},
    )


@router.get("/finance/capital-sources/export/pdf")
async def capital_sources_pdf(_: dict = Depends(get_current_user)):
    sources = await db.funding_sources.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for r in sources:
        repaid = await db.funding_repayments.find({"source_id": r["id"]}, {"_id": 0}).to_list(500)
        total_repaid = sum(float(x.get("amount", 0) or 0) for x in repaid)
        r["total_repaid"] = round(total_repaid, 2)
        r["outstanding"] = round(max(0.0, float(r["principal_amount"]) - total_repaid), 2)
    pdf_bytes = build_capital_sources_pdf(sources)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="capital-sources.pdf"'},
    )


@router.get("/finance/expenses/export/pdf")
async def expenses_pdf(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    category: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    rows = await db.expenses.find({}, {"_id": 0}).sort("date", -1).to_list(5000)
    rows = _apply_date_filter(rows, "date", month, year)
    if category:
        rows = [r for r in rows if r.get("category") == category]

    by_category_list: list[dict] = []
    if not category:
        by_cat: dict[str, float] = {}
        for e in rows:
            cat = e.get("category", "Other")
            by_cat[cat] = by_cat.get(cat, 0.0) + float(e.get("amount", 0) or 0)
        by_category_list = [{"category": k, "amount": round(v, 2)} for k, v in by_cat.items()]

    pdf_bytes = build_expenses_pdf(
        rows, category=category, month=month, year=year, by_category=by_category_list or None,
    )
    fname = f"expenses-{category}.pdf" if category else "expenses.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )

