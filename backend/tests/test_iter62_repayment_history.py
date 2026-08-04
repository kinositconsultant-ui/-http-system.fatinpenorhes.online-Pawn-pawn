"""Iter 62 — Repayment History Drawer + Reversal.

Verifies:
- GET /funding-sources/{sid}/repayments backfills principal/interest split for legacy rows
- DELETE /funding-sources/{sid}/repayments/{rid} reverses BOTH the outstanding
  balance and the linked interest expense
- Cash on Hand, Capital Outstanding, and Net Profit all restore to pre-repayment
  values after a delete
"""
import os
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


def _summary(s):
    return s.get(f"{API}/finance/summary", timeout=15).json()


@pytest.fixture
def source(s):
    src = s.post(f"{API}/funding-sources", json={
        "name": f"pytest-iter62-{os.getpid()}",
        "source_type": "bank",
        "principal_amount": 5000.0,
        "interest_rate": 5.0,
        "interest_period": "monthly",
        "term_months": 12,
        "start_date": "2026-01-01",
    }, timeout=15).json()
    yield src
    s.delete(f"{API}/funding-sources/{src['id']}", timeout=15)


def test_list_repayments_backfills_split_fields(s, source):
    """GET should always return principal_amount + interest_amount fields
    even for legacy docs that only have `amount`."""
    # Post a legacy-shape repayment (amount-only)
    r = s.post(f"{API}/funding-sources/{source['id']}/repayments", json={
        "source_id": source["id"], "amount": 300, "date": "2026-02-04",
    }, timeout=15)
    assert r.status_code == 200

    rows = s.get(f"{API}/funding-sources/{source['id']}/repayments", timeout=15).json()
    assert len(rows) == 1
    assert rows[0]["principal_amount"] == 300.0
    assert rows[0]["interest_amount"] == 0.0
    assert rows[0]["amount"] == 300.0


def test_delete_repayment_reverses_all_three_effects(s, source):
    """Deleting a mixed repayment must restore outstanding, financial expense,
    and net profit."""
    before = _summary(s)
    # Post $400 principal + $100 interest
    r = s.post(f"{API}/funding-sources/{source['id']}/repayments", json={
        "source_id": source["id"], "principal_amount": 400, "interest_amount": 100,
        "date": "2026-02-04",
    }, timeout=15)
    assert r.status_code == 200
    rid = r.json()["id"]

    after_post = _summary(s)
    assert after_post["capital_outstanding"] == pytest.approx(before["capital_outstanding"] - 400, abs=0.01)
    assert after_post["financial_expenses"] == pytest.approx(before["financial_expenses"] + 100, abs=0.01)
    assert after_post["net_profit"] == pytest.approx(before["net_profit"] - 100, abs=0.01)

    # DELETE
    d = s.delete(f"{API}/funding-sources/{source['id']}/repayments/{rid}", timeout=15)
    assert d.status_code == 200, d.text

    after_del = _summary(s)
    # Everything back to pre-repayment
    assert after_del["capital_outstanding"] == pytest.approx(before["capital_outstanding"], abs=0.01)
    assert after_del["financial_expenses"] == pytest.approx(before["financial_expenses"], abs=0.01)
    assert after_del["net_profit"] == pytest.approx(before["net_profit"], abs=0.01)

    # Repayment gone from list
    rows = s.get(f"{API}/funding-sources/{source['id']}/repayments", timeout=15).json()
    assert all(r["id"] != rid for r in rows)


def test_delete_nonexistent_repayment_returns_404(s, source):
    d = s.delete(f"{API}/funding-sources/{source['id']}/repayments/doesnotexist", timeout=15)
    assert d.status_code == 404
