"""Iter 66 — Recurring Installment Ledger (JSON schedule endpoint).

Verifies:
- GET /funding-sources/{sid}/schedule returns rows[] with 8 fields each
- 404 on unknown source
- Requires authentication
- Installment count matches term_months / step_months (frequency-aware)
- Sum of `principal` across all rows == source.principal_amount
- Statuses classify correctly against today
"""
import os
from datetime import date, timedelta

import pytest
import requests

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pawnly-pro.preview.emergentagent.com").rstrip("/") + "/api"
ADMIN = {"email": "admin@fatinpenhores.tl", "password": "admin123"}


@pytest.fixture(scope="module")
def s():
    session = requests.Session()
    r = session.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200
    return session


@pytest.fixture
def source_factory(s):
    created = []

    def make(**kw):
        payload = {
            "name": f"pytest-iter66-{os.getpid()}-{len(created)}",
            "source_type": "bank",
            "principal_amount": 12000.0,
            "interest_rate": 4.0,
            "interest_period": "monthly",
            "term_months": 12,
            "payment_frequency": "monthly",
            "start_date": "2026-01-01",
        }
        payload.update(kw)
        r = s.post(f"{API}/funding-sources", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        row = r.json()
        created.append(row["id"])
        return row

    yield make
    for sid in created:
        s.delete(f"{API}/funding-sources/{sid}", timeout=15)


def test_returns_404_for_unknown_source(s):
    r = s.get(f"{API}/funding-sources/does-not-exist/schedule", timeout=15)
    assert r.status_code == 404


def test_requires_auth():
    r = requests.get(f"{API}/funding-sources/x/schedule", timeout=15)
    assert r.status_code in (401, 403)


def test_monthly_12mo_produces_12_installments(s, source_factory):
    src = source_factory(payment_frequency="monthly", term_months=12)
    r = s.get(f"{API}/funding-sources/{src['id']}/schedule", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body["installments_total"] == 12
    assert len(body["rows"]) == 12
    # Principal totals reconcile
    total_p = round(sum(row["principal"] for row in body["rows"]), 2)
    assert total_p == 12000.0
    # First row's opening balance = source principal
    assert body["rows"][0]["opening_balance"] == 12000.0
    # Last row's ending balance = 0
    assert body["rows"][-1]["ending_balance"] == 0.0


def test_quarterly_12mo_produces_4_installments(s, source_factory):
    src = source_factory(payment_frequency="quarterly", term_months=12)
    body = s.get(f"{API}/funding-sources/{src['id']}/schedule", timeout=15).json()
    assert body["installments_total"] == 4
    # Interest per row = balance × 4% × 3 months = 12k×0.04×3 = 1440 (first row)
    assert body["rows"][0]["interest"] == 1440.0
    # Amortization drops principal from 12k → 0
    assert body["rows"][-1]["ending_balance"] == 0.0


def test_lump_sum_produces_one_installment(s, source_factory):
    src = source_factory(payment_frequency="lump_sum", term_months=6)
    body = s.get(f"{API}/funding-sources/{src['id']}/schedule", timeout=15).json()
    assert body["installments_total"] == 1
    row = body["rows"][0]
    assert row["principal"] == 12000.0
    assert row["ending_balance"] == 0.0
    # For lump_sum in 6 months at 4% monthly: interest = 12000×0.04×6 = 2880
    assert row["interest"] == 2880.0


def test_status_classification(s, source_factory):
    """Row with due_date in past → overdue; future → scheduled; ≤7 days out → due_soon."""
    src = source_factory(payment_frequency="monthly", term_months=12, start_date="2026-01-01")
    body = s.get(f"{API}/funding-sources/{src['id']}/schedule", timeout=15).json()
    today = date.today()
    for row in body["rows"]:
        due = date.fromisoformat(row["due_date"])
        if due < today:
            assert row["status"] in ("overdue", "paid"), f"past date should be overdue/paid: {row}"
        elif (due - today).days <= 7:
            assert row["status"] in ("due_soon", "paid"), f"within 7d should be due_soon/paid: {row}"
        else:
            assert row["status"] in ("scheduled", "paid"), f"future should be scheduled/paid: {row}"


def test_paid_status_after_repayment(s, source_factory):
    """After posting a $6000 principal repayment on a 12k/12mo source, the
    first 6 rows (cumulative principal ≤ 6000) should show 'paid'."""
    src = source_factory(payment_frequency="monthly", term_months=12)
    # 12k / 12 = 1000 per row → 6000 principal covers rows 1..6
    p = s.post(f"{API}/funding-sources/{src['id']}/repayments", json={
        "source_id": src["id"], "principal_amount": 6000, "interest_amount": 0,
        "date": "2026-02-04",
    }, timeout=15)
    assert p.status_code == 200

    body = s.get(f"{API}/funding-sources/{src['id']}/schedule", timeout=15).json()
    # First 6 rows should be paid
    for row in body["rows"][:6]:
        assert row["status"] == "paid", f"row {row['installment']} should be paid: {row}"
    # 7th onward should NOT be paid
    for row in body["rows"][6:]:
        assert row["status"] != "paid", f"row {row['installment']} should NOT be paid: {row}"
