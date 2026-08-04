"""Contract KPIs & expiring-soon notifications (iter 62 · Phase F).

New endpoints:

  GET /api/contracts/kpis
     Returns aggregate KPIs for the Contracts page header and a list of
     "expiring in month 2" contracts with client contact info, ready for
     staff follow-up.

  GET /api/contracts/expiring?days_ahead=7|30
     Returns contracts whose due_date falls in the next N days with client
     contact info — used by the Contracts page notification panel and the
     Dashboard alert widget.

Definitions:
  * Month 2 = contract_date is between 30 and 60 days ago (today ∈ 2nd
    month of the pawn cycle). Under Fatin Penhores rules the interest cap
    kicks in at month 2, so this is the crunch bucket.
  * Active exposure = principal_remaining across contracts whose status is
    active, grace_period, overdue, or auction_ready. We do NOT include
    sold/redeemed/auction contracts (they are already resolved).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from deps import db, get_current_user

router = APIRouter(tags=["contracts-kpi"])

ACTIVE_STATUSES = {"active", "grace_period", "overdue", "auction_ready"}


def _today() -> date:
    return date.today()


def _parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


@router.get("/contracts/kpis")
async def contracts_kpis(_: dict = Depends(get_current_user)):
    """Everything the Contracts page needs for its KPI header + notifications."""
    contracts = await db.contracts.find({}, {"_id": 0}).to_list(10000)
    clients = await db.clients.find(
        {}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1}
    ).to_list(5000)
    client_map = {c["id"]: c for c in clients}

    today = _today()
    month2_lo = today - timedelta(days=60)
    month2_hi = today - timedelta(days=30)

    active_count = 0
    active_client_ids: set[str] = set()
    total_principal_remaining = 0.0
    total_loan_amount = 0.0
    projected_month2_interest = 0.0
    expiring_month2: list[dict] = []
    expiring_next_7: list[dict] = []
    expiring_next_30: list[dict] = []

    for c in contracts:
        status = c.get("status", "active")
        if status not in ACTIVE_STATUSES:
            continue
        active_count += 1
        cid_client = c.get("client_id")
        if cid_client:
            active_client_ids.add(cid_client)
        principal_remaining = float(c.get("principal_remaining", c.get("loan_amount", 0)) or 0)
        loan_amount = float(c.get("loan_amount", 0) or 0)
        rate = float(c.get("interest_rate", 0) or 0)
        total_principal_remaining += principal_remaining
        total_loan_amount += loan_amount
        # Projected month-2 interest: interest that will be billed once the
        # contract enters its second month. Capped at 2 months per policy.
        interest_month = principal_remaining * rate / 100.0
        interest_paid = float(c.get("interest_paid", 0) or 0)
        # If the contract is only entering month 2 today, project one more month
        # of interest on top of what's already paid; if it's already past 2
        # months, the cap is applied so no further interest accrues.
        projected_month2_interest += max(0.0, interest_month * 2 - interest_paid)

        cdate = _parse_date(c.get("contract_date"))
        ddate = _parse_date(c.get("due_date"))
        client = client_map.get(cid_client, {})
        entry = {
            "id": c["id"],
            "contract_number": c.get("contract_number"),
            "item_type": c.get("item_type"),
            "status": status,
            "loan_amount": loan_amount,
            "principal_remaining": principal_remaining,
            "interest_rate": rate,
            "contract_date": c.get("contract_date"),
            "due_date": c.get("due_date"),
            "days_until_due": (ddate - today).days if ddate else None,
            "days_in_contract": (today - cdate).days if cdate else None,
            "client_id": cid_client,
            "client_name": client.get("full_name"),
            "client_phone": client.get("phone"),
            "client_email": client.get("email"),
        }

        # Month-2 bucket: contract_date is between 30 and 60 days ago.
        if cdate and month2_lo <= cdate < month2_hi:
            expiring_month2.append(entry)

        # Expiring-soon buckets by due_date proximity.
        if ddate:
            delta = (ddate - today).days
            if 0 <= delta <= 7:
                expiring_next_7.append(entry)
            if 0 <= delta <= 30:
                expiring_next_30.append(entry)

    # Sort notification lists by soonest first
    expiring_month2.sort(key=lambda e: e.get("due_date") or "")
    expiring_next_7.sort(key=lambda e: e.get("days_until_due") or 999)
    expiring_next_30.sort(key=lambda e: e.get("days_until_due") or 999)

    return {
        "active_contracts": active_count,
        "active_clients": len(active_client_ids),
        "total_loan_amount": round(total_loan_amount, 2),
        "total_principal_remaining": round(total_principal_remaining, 2),
        "projected_month2_interest": round(projected_month2_interest, 2),
        "month2_count": len(expiring_month2),
        "expiring_next_7_count": len(expiring_next_7),
        "expiring_next_30_count": len(expiring_next_30),
        "expiring_month2": expiring_month2,
        "expiring_next_7": expiring_next_7,
        "expiring_next_30": expiring_next_30,
    }


@router.get("/contracts/expiring")
async def contracts_expiring(
    days_ahead: int = Query(7, ge=0, le=90),
    scope: Literal["due_date", "month_2"] = Query("due_date"),
    _: dict = Depends(get_current_user),
):
    """Standalone list variant. `scope=due_date` uses the contract's due_date
    (default 7 days ahead). `scope=month_2` returns contracts currently in
    their second month regardless of `days_ahead`."""
    kpis = await contracts_kpis(_=_)
    if scope == "month_2":
        return kpis["expiring_month2"]
    if days_ahead <= 7:
        return kpis["expiring_next_7"]
    return kpis["expiring_next_30"]
