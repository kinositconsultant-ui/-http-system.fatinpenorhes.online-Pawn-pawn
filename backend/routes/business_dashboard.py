"""Business Dashboard aggregate (iter 65).

One endpoint powers the Director's dashboard so a single request returns
every KPI + notification bucket. Everything is composed from existing
collections — nothing new is persisted.

GET /api/business/dashboard  → keys:
  active_clients, active_contracts, total_principal_remaining, total_loan_amount
  active_items_count, active_items_market_value
  warehouse_items_count, office_items_count
  cash_on_hand
  month_interest_received, month_penalty_received
  month_full_payments_count, month_full_payments_total
  month_auctions_count, month_auctions_total
  month_inspections_reimbursed
  auction_profit_lifetime, gross_profit_lifetime, net_profit_lifetime
  expiring_7 / expiring_15 / expiring_month2  (counts + lists)
  upcoming_loan_repayments
  as_of  (server ISO timestamp for the client to display "updated at")
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from deps import db, COLLECTION_MAP, require_module

router = APIRouter(tags=["business-dashboard"])

ACTIVE_STATUSES = {"active", "grace_period", "overdue", "auction_ready"}
WAREHOUSE_KINDS = ("car", "motorcycle", "pezadu")
OFFICE_KINDS = ("electronic",)
FULL_PAYMENT_TYPES = {"full", "overdue_full"}


def _month_bounds(today: date) -> tuple[str, str]:
    first = today.replace(day=1)
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1)
    else:
        nxt = first.replace(month=first.month + 1)
    return first.isoformat(), nxt.isoformat()


@router.get("/business/dashboard")
async def business_dashboard(_: dict = Depends(require_module("dashboard"))):
    today = date.today()
    today_iso = today.isoformat()
    month_start, month_end = _month_bounds(today)
    d7 = (today + timedelta(days=7)).isoformat()
    d15 = (today + timedelta(days=15)).isoformat()
    month2_lo = (today - timedelta(days=60)).isoformat()
    month2_hi = (today - timedelta(days=30)).isoformat()

    # ---- Contracts ------------------------------------------------------
    contracts = await db.contracts.find({}, {"_id": 0}).to_list(20000)
    active_contracts = 0
    active_client_ids: set[str] = set()
    total_loan = 0.0
    total_principal = 0.0
    active_item_ids: set[str] = set()
    expiring_7: list[dict] = []
    expiring_15: list[dict] = []
    expiring_month2: list[dict] = []
    for c in contracts:
        st = c.get("status") or "active"
        if st not in ACTIVE_STATUSES:
            continue
        active_contracts += 1
        if c.get("client_id"):
            active_client_ids.add(c["client_id"])
        if c.get("item_id"):
            active_item_ids.add(c["item_id"])
        total_loan += float(c.get("loan_amount", 0) or 0)
        total_principal += float(c.get("principal_remaining", c.get("loan_amount", 0)) or 0)
        dd = c.get("due_date") or ""
        if dd and today_iso <= dd <= d7:
            expiring_7.append(c)
        if dd and today_iso <= dd <= d15:
            expiring_15.append(c)
        cd = c.get("contract_date") or ""
        if cd and month2_lo <= cd < month2_hi:
            expiring_month2.append(c)

    # Enrich expiring lists with client info (lightweight)
    clients = await db.clients.find(
        {}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1}
    ).to_list(5000)
    cmap = {c["id"]: c for c in clients}

    def _enrich(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            cl = cmap.get(r.get("client_id"), {})
            out.append({
                "id": r.get("id"),
                "contract_number": r.get("contract_number"),
                "due_date": r.get("due_date"),
                "contract_date": r.get("contract_date"),
                "status": r.get("status"),
                "item_type": r.get("item_type"),
                "principal_remaining": float(r.get("principal_remaining", r.get("loan_amount", 0)) or 0),
                "client_name": cl.get("full_name"),
                "client_phone": cl.get("phone"),
                "client_email": cl.get("email"),
            })
        return sorted(out, key=lambda x: x.get("due_date") or "")

    # ---- Items (active split warehouse/office) -------------------------
    active_items_count = 0
    active_items_value = 0.0
    warehouse_items_count = 0
    office_items_count = 0
    for kind in WAREHOUSE_KINDS + OFFICE_KINDS:
        coll = db[COLLECTION_MAP[kind]]
        async for it in coll.find({}, {"_id": 0, "id": 1, "market_value": 1}):
            if it.get("id") not in active_item_ids:
                continue
            active_items_count += 1
            v = float(it.get("market_value", 0) or 0)
            active_items_value += v
            if kind in WAREHOUSE_KINDS:
                warehouse_items_count += 1
            else:
                office_items_count += 1

    # ---- Payments (month rollups) --------------------------------------
    month_interest_received = 0.0
    month_penalty_received = 0.0
    month_full_payments_count = 0
    month_full_payments_total = 0.0
    async for p in db.payments.find({"date": {"$gte": month_start, "$lt": month_end}}, {"_id": 0}):
        t = p.get("type") or ""
        amt = float(p.get("amount", 0) or 0)
        if t == "interest_only":
            month_interest_received += amt
        elif t == "partial":
            month_interest_received += amt
        elif t in ("overdue_penalty_only",):
            month_penalty_received += amt
        elif t == "overdue_interest_pen":
            month_interest_received += amt / 2
            month_penalty_received += amt / 2
        elif t in FULL_PAYMENT_TYPES:
            month_full_payments_count += 1
            month_full_payments_total += amt

    # ---- Auctions (month rollups + lifetime profit) --------------------
    month_auctions_count = 0
    month_auctions_total = 0.0
    auction_profit_lifetime = 0.0
    auction_interest_lifetime = 0.0
    auction_realized_lifetime = 0.0
    auction_realized_loss_lifetime = 0.0
    async for a in db.auctions.find({}, {"_id": 0}):
        ds = a.get("date_sold") or ""
        if a.get("sold_price"):
            if month_start <= ds < month_end:
                month_auctions_count += 1
                month_auctions_total += float(a.get("sold_price", 0) or 0)
        auction_interest_lifetime += float(a.get("interest_profit", 0) or 0)
        auction_realized_lifetime += float(a.get("realized_profit", 0) or 0)
        auction_realized_loss_lifetime += float(a.get("realized_loss", 0) or 0)
    auction_profit_lifetime = (
        auction_interest_lifetime + auction_realized_lifetime - auction_realized_loss_lifetime
    )

    # ---- Interest & penalty lifetime (from contracts) ------------------
    interest_received_lifetime = sum(float(c.get("interest_paid", 0) or 0) for c in contracts)
    total_penalty_lifetime = sum(float(c.get("penalty_paid", 0) or 0) for c in contracts)
    gross_profit_lifetime = (
        interest_received_lifetime + total_penalty_lifetime + auction_profit_lifetime
    )

    # ---- Inspections ---------------------------------------------------
    inspections_incurred = 0.0
    inspections_reimbursed = 0.0
    month_inspections_reimbursed = 0.0
    async for ins in db.inspections.find({}, {"_id": 0}):
        inspections_incurred += float(ins.get("amount", 0) or 0)
        r = float(ins.get("reimbursed_amount", 0) or 0)
        inspections_reimbursed += r
        rd = ins.get("reimbursed_date") or ""
        if ins.get("reimbursed") and month_start <= rd < month_end:
            month_inspections_reimbursed += r

    # ---- Expenses (lifetime + month) -----------------------------------
    expenses_total = 0.0
    async for e in db.expenses.find({}, {"_id": 0, "amount": 1}):
        expenses_total += float(e.get("amount", 0) or 0)
    net_profit_lifetime = gross_profit_lifetime - expenses_total

    # ---- Cash on Hand --------------------------------------------------
    settings_doc = await db.settings.find_one({}, {"_id": 0}) or {}
    opening_cash = float(settings_doc.get("opening_cash_balance", 0) or 0)
    # Capital in
    capital_in = 0.0
    async for f in db.funding_sources.find({}, {"_id": 0, "principal_amount": 1}):
        capital_in += float(f.get("principal_amount", 0) or 0)
    capital_out = 0.0
    async for r in db.funding_repayments.find({}, {"_id": 0, "amount": 1}):
        capital_out += float(r.get("amount", 0) or 0)
    # Payments split (disbursement = out, others = in)
    client_pay_in = 0.0
    loans_out = 0.0
    async for p in db.payments.find({}, {"_id": 0, "type": 1, "amount": 1}):
        a = float(p.get("amount", 0) or 0)
        if p.get("type") == "disbursement":
            loans_out += a
        else:
            client_pay_in += a
    # Auctions & tax
    auction_in = 0.0
    tax_in = 0.0
    async for a in db.auctions.find({}, {"_id": 0, "sold_price": 1, "tax_collected": 1}):
        auction_in += float(a.get("sold_price", 0) or 0)
        tax_in += float(a.get("tax_collected", 0) or 0)
    cash_on_hand = (
        opening_cash + capital_in + client_pay_in + auction_in + tax_in + inspections_reimbursed
        - loans_out - expenses_total - capital_out - inspections_incurred
    )

    # ---- Upcoming loan repayments (next 30 days, unpaid) ---------------
    horizon = (today + timedelta(days=30)).isoformat()
    upcoming: list[dict] = []
    for s in await db.funding_sources.find({}, {"_id": 0}).to_list(200):
        due = s.get("due_date") or ""
        if not due or due > horizon:
            continue
        repays = await db.funding_repayments.find(
            {"funding_source_id": s.get("id")}, {"_id": 0, "amount": 1}
        ).to_list(500)
        repaid = sum(float(r.get("amount", 0) or 0) for r in repays)
        outstanding = max(0.0, float(s.get("principal_amount", 0) or 0) - repaid)
        if outstanding <= 0:
            continue
        try:
            du = (date.fromisoformat(due) - today).days
        except Exception:
            du = None
        upcoming.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "source_type": s.get("source_type"),
            "outstanding": round(outstanding, 2),
            "due_date": due,
            "days_until_due": du,
        })
    upcoming.sort(key=lambda x: x["due_date"])

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "month_from": month_start,
        "month_to": month_end,
        # Portfolio KPIs
        "active_clients": len(active_client_ids),
        "active_contracts": active_contracts,
        "total_loan_amount": round(total_loan, 2),
        "total_principal_remaining": round(total_principal, 2),
        "active_items_count": active_items_count,
        "active_items_market_value": round(active_items_value, 2),
        "warehouse_items_count": warehouse_items_count,
        "office_items_count": office_items_count,
        "cash_on_hand": round(cash_on_hand, 2),
        # Month-scoped
        "month_interest_received": round(month_interest_received, 2),
        "month_penalty_received": round(month_penalty_received, 2),
        "month_full_payments_count": month_full_payments_count,
        "month_full_payments_total": round(month_full_payments_total, 2),
        "month_auctions_count": month_auctions_count,
        "month_auctions_total": round(month_auctions_total, 2),
        "month_inspections_reimbursed": round(month_inspections_reimbursed, 2),
        # Lifetime profit
        "auction_profit_lifetime": round(auction_profit_lifetime, 2),
        "gross_profit_lifetime": round(gross_profit_lifetime, 2),
        "net_profit_lifetime": round(net_profit_lifetime, 2),
        # Notification buckets
        "expiring_7_count": len(expiring_7),
        "expiring_15_count": len(expiring_15),
        "expiring_month2_count": len(expiring_month2),
        "expiring_7": _enrich(expiring_7)[:20],
        "expiring_15": _enrich(expiring_15)[:20],
        "expiring_month2": _enrich(expiring_month2)[:20],
        "upcoming_loan_repayments": upcoming,
    }
