"""Iteration 37 — Contracts / Overdue / Financial Reports logic overhaul (Nov-2026 spec).

Verifies the client-mandated rules:
1. Active Contracts "Total Loan" KPI = SUM of current_principal (not original loan).
2. Financial Report "profit" = interest_paid + penalty_paid (never adds unpaid penalty).
3. Payments Report "total_penalty" = penalty ACTUALLY paid, not remaining/charged.
4. Contracts expose normalized fields: original_loan_amount, current_principal,
   penalty_charged, penalty_paid, penalty_outstanding, total_amount_due.
5. Penalty for overdue contracts scales with CURRENT principal (not original).
6. Finance summary exposes auction_capital_recovered / auction_realized_profit /
   auction_realized_loss split.
"""
from __future__ import annotations

import io
import os
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def api_sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@fatinpenhores.tl", "password": "admin123"})
    assert r.status_code == 200
    return s


def test_active_report_total_loan_uses_current_principal(api_sess):
    """Active Contracts Total Loan KPI must equal SUM of principal_remaining."""
    r = api_sess.get(f"{BASE_URL}/api/reports/v2/active-contracts")
    assert r.status_code == 200
    data = r.json()
    expected = round(
        sum(float(row.get("principal_remaining", 0) or 0) for row in data["rows"]), 2
    )
    assert data["kpis"]["total_loan"] == expected, (
        f"KPI ({data['kpis']['total_loan']}) must equal SUM(principal_remaining) ({expected})"
    )


def test_financial_report_profit_excludes_unpaid_penalty(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/reports/v2/financial")
    assert r.status_code == 200
    kpis = r.json()["kpis"]
    # Profit MUST equal interest_received + penalty_paid exactly. Never adds
    # penalty_outstanding.
    expected_profit = round(kpis["interest_received"] + kpis["penalty_paid"], 2)
    assert kpis["profit"] == expected_profit
    # Regression guard: if there's any outstanding penalty, it MUST NOT sneak
    # into profit.
    if kpis.get("penalty_outstanding", 0) > 0:
        assert kpis["profit"] != kpis["interest_received"] + kpis["penalty_outstanding"]


def test_payments_total_penalty_is_penalty_paid(api_sess):
    """Payments report total_penalty KPI must reflect penalty PAID, not remaining."""
    p = api_sess.get(f"{BASE_URL}/api/reports/v2/payments").json()
    f = api_sess.get(f"{BASE_URL}/api/reports/v2/financial").json()
    # Both KPIs should agree that penalty_paid == total_penalty
    assert p["kpis"]["total_penalty"] == f["kpis"]["penalty_paid"], (
        f"payments.total_penalty ({p['kpis']['total_penalty']}) should equal "
        f"financial.penalty_paid ({f['kpis']['penalty_paid']})"
    )


def test_contracts_expose_normalized_fields(api_sess):
    """Every contract should have the new charged/paid/outstanding fields."""
    contracts = api_sess.get(f"{BASE_URL}/api/reports/v2/active-contracts").json()["rows"]
    if not contracts:
        pytest.skip("no active contracts in test env")
    c = contracts[0]
    required = [
        "original_loan_amount", "current_principal", "principal_paid",
        "interest_charged", "interest_paid", "interest_outstanding",
        "penalty_charged", "penalty_paid", "penalty_outstanding",
        "total_amount_due", "total_payments_received",
    ]
    missing = [k for k in required if k not in c]
    assert not missing, f"missing normalized fields: {missing}"


def test_penalty_scales_with_current_principal():
    """For an overdue contract, penalty must equal current_principal × penalty_rate.

    Uses a fresh contract created via API so we get deterministic numbers.
    """
    s = requests.Session()
    s.post(f"{BASE_URL}/api/auth/login",
           json={"email": "admin@fatinpenhores.tl", "password": "admin123"})
    tag = uuid.uuid4().hex[:6]
    # 1. Client
    cr = s.post(f"{BASE_URL}/api/clients", json={
        "full_name": f"Penalty Test {tag}", "id_type": "BI",
        "id_number": f"PT-{tag}", "phone": "+670-1",
    })
    cid = cr.json()["id"]
    # 2. Car item
    ir = s.post(f"{BASE_URL}/api/items/car", json={
        "name": f"Car {tag}", "brand": "Toyota", "model": "Test",
        "market_value": 5000,
    })
    iid = ir.json()["id"]
    # 3. Contract $3000 @ 10% — just barely overdue so only 1 month billed.
    # This way a $1000 partial pays off $300 interest + $700 principal (M1).
    from datetime import date, timedelta
    old = (date.today() - timedelta(days=31)).isoformat()
    due = (date.today() - timedelta(days=1)).isoformat()  # 1 day overdue
    ctr = s.post(f"{BASE_URL}/api/contracts", json={
        "client_id": cid, "item_type": "car", "item_id": iid,
        "loan_amount": 3000, "interest_rate": 10.0,
        "contract_date": old, "due_date": due,
    })
    assert ctr.status_code == 200
    contract_id = ctr.json()["id"]

    try:
        # Fetch and check initial penalty = 3000 * 10% = 300
        got = s.get(f"{BASE_URL}/api/contracts/{contract_id}").json()
        assert got["status"] in ("overdue", "auction_ready"), got["status"]
        # Interest owed for months elapsed varies with test date; the key
        # invariant is penalty_charged == current_principal × 10%
        assert got["penalty_charged"] == round(got["current_principal"] * 10.0 / 100.0, 2), (
            f"penalty {got['penalty_charged']} should equal current_principal ({got['current_principal']}) × 10%"
        )
        # 4. Client pays $1000 partial (interest first, then principal)
        s.post(f"{BASE_URL}/api/payments", json={
            "contract_id": contract_id, "amount": 1000, "type": "partial",
            "date": date.today().isoformat(),
        })
        got2 = s.get(f"{BASE_URL}/api/contracts/{contract_id}").json()
        # After the payment, penalty_charged must have adjusted to the NEW
        # current_principal × 10%
        assert got2["penalty_charged"] == round(got2["current_principal"] * 10.0 / 100.0, 2), (
            f"after partial: penalty {got2['penalty_charged']} should equal "
            f"current_principal ({got2['current_principal']}) × 10%"
        )
        # And principal MUST have dropped ($1000 pays $600 interest + $400 principal)
        assert got2["current_principal"] < 3000, "principal should have dropped"
    finally:
        s.delete(f"{BASE_URL}/api/contracts/{contract_id}")
        s.delete(f"{BASE_URL}/api/items/car/{iid}")
        s.delete(f"{BASE_URL}/api/clients/{cid}")


def test_finance_summary_exposes_auction_split(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/finance/summary")
    assert r.status_code == 200
    data = r.json()
    for key in ("auction_capital_recovered", "auction_realized_profit", "auction_realized_loss"):
        assert key in data, f"finance/summary missing {key}"
    # The three components must sum to auction_sales (or exceed it by
    # loss — because loss is capital NOT recovered).
    # capital_recovered + profit = sold_price; loss + capital_recovered = original_loan
    # so: auction_sales = capital_recovered + profit - 0 (loss cancels out on sales value)
    total_check = data["auction_capital_recovered"] + data["auction_realized_profit"]
    # allow floating tolerance
    assert abs(total_check - data["auction_sales"]) < 1.0, (
        f"capital_recovered + profit ({total_check}) should ≈ auction_sales ({data['auction_sales']})"
    )
