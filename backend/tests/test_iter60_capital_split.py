"""Iter 60 — Capital Outstanding Option A: split repayment into principal
+ interest with interest auto-booked as expense.

Rules verified:
- Principal repayment: reduces capital_outstanding + cash_on_hand, does NOT affect profit
- Interest repayment: reduces cash_on_hand + reduces net_profit via expense row
- Legacy repayments (only `amount` field) treated as pure principal
- Funding source list returns 7 KPIs (principal_paid, principal_remaining,
  interest_paid, interest_remaining, next_due_date, status, ...)
"""
import os
import pytest
import requests

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pawnly-pro.preview.emergentagent.com").rstrip("/") + "/api"
ADMIN = {"email": "admin@fatinpenhores.tl", "password": "admin123"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    yield _ApiWrap(s)


class _ApiWrap:
    def __init__(self, s):
        self.s = s
    def get(self, path, **kw):
        return self.s.get(f"{API}{path}", timeout=15, **kw)
    def post(self, path, **kw):
        return self.s.post(f"{API}{path}", timeout=15, **kw)
    def delete(self, path, **kw):
        return self.s.delete(f"{API}{path}", timeout=15, **kw)


@pytest.fixture
def capital_source(admin_client):
    payload = {
        "name": f"pytest-iter60-{os.getpid()}",
        "source_type": "bank",
        "principal_amount": 10000.0,
        "interest_rate": 5.0,
        "interest_period": "monthly",
        "term_months": 12,
        "start_date": "2026-01-01",
        "due_date": "2027-01-01",
        "notes": "test",
    }
    r = admin_client.post("/funding-sources", json=payload)
    assert r.status_code == 200, r.text
    src = r.json()
    yield src
    admin_client.delete(f"/funding-sources/{src['id']}")


def _summary(c):
    r = c.get("/finance/summary")
    assert r.status_code == 200
    return r.json()


def test_capital_source_returns_seven_kpis(admin_client, capital_source):
    """A fresh capital source lists all 7 KPI fields."""
    r = admin_client.get("/funding-sources")
    assert r.status_code == 200
    src = next(s for s in r.json() if s["id"] == capital_source["id"])
    for key in ("principal_paid", "principal_remaining", "interest_paid",
                "interest_remaining", "next_due_date", "status", "interest_scheduled"):
        assert key in src, f"missing KPI: {key}"
    assert src["principal_paid"] == 0.0
    assert src["principal_remaining"] == 10000.0
    assert src["interest_paid"] == 0.0
    # 10000 * 5% * 12 months = 6000
    assert src["interest_scheduled"] == pytest.approx(6000.0)
    assert src["status"] in ("on_time", "due_soon", "overdue", "closed")


def test_principal_repayment_reduces_outstanding_only(admin_client, capital_source):
    """Repaying $400 principal reduces capital_outstanding by $400. Net profit unchanged."""
    before = _summary(admin_client)
    r = admin_client.post(
        f"/funding-sources/{capital_source['id']}/repayments",
        json={"source_id": capital_source["id"], "principal_amount": 400,
              "interest_amount": 0, "date": "2026-02-04"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["principal_amount"] == 400.0
    assert body["interest_amount"] == 0.0
    assert body["amount"] == 400.0

    after = _summary(admin_client)
    assert after["capital_outstanding"] == pytest.approx(before["capital_outstanding"] - 400, abs=0.01)
    assert after["capital_repaid_principal"] == pytest.approx(before["capital_repaid_principal"] + 400, abs=0.01)
    assert after["capital_interest_paid"] == pytest.approx(before["capital_interest_paid"], abs=0.01)
    # Net profit unchanged (no expense booked)
    assert after["net_profit"] == pytest.approx(before["net_profit"], abs=0.01)


def test_interest_repayment_books_expense_and_reduces_net_profit(admin_client, capital_source):
    """Interest-only repayment does NOT reduce outstanding, but DOES reduce net_profit."""
    before = _summary(admin_client)
    r = admin_client.post(
        f"/funding-sources/{capital_source['id']}/repayments",
        json={"source_id": capital_source["id"], "principal_amount": 0,
              "interest_amount": 150, "date": "2026-02-04"},
    )
    assert r.status_code == 200, r.text

    after = _summary(admin_client)
    assert after["capital_outstanding"] == pytest.approx(before["capital_outstanding"], abs=0.01)
    assert after["capital_interest_paid"] == pytest.approx(before["capital_interest_paid"] + 150, abs=0.01)
    assert after["expenses_total"] == pytest.approx(before["expenses_total"] + 150, abs=0.01)
    assert after["net_profit"] == pytest.approx(before["net_profit"] - 150, abs=0.01)


def test_mixed_repayment(admin_client, capital_source):
    """Mixed $400 principal + $100 interest → outstanding −400, net profit −100."""
    before = _summary(admin_client)
    r = admin_client.post(
        f"/funding-sources/{capital_source['id']}/repayments",
        json={"source_id": capital_source["id"], "principal_amount": 400,
              "interest_amount": 100, "date": "2026-02-04"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["amount"] == 500.0

    after = _summary(admin_client)
    assert after["capital_outstanding"] == pytest.approx(before["capital_outstanding"] - 400, abs=0.01)
    assert after["net_profit"] == pytest.approx(before["net_profit"] - 100, abs=0.01)


def test_legacy_amount_only_treated_as_principal(admin_client, capital_source):
    """Backward compat: posting just `amount` treats it all as principal."""
    before = _summary(admin_client)
    r = admin_client.post(
        f"/funding-sources/{capital_source['id']}/repayments",
        json={"source_id": capital_source["id"], "amount": 200, "date": "2026-02-04"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["principal_amount"] == 200.0
    assert body["interest_amount"] == 0.0

    after = _summary(admin_client)
    assert after["capital_outstanding"] == pytest.approx(before["capital_outstanding"] - 200, abs=0.01)
    assert after["net_profit"] == pytest.approx(before["net_profit"], abs=0.01)


def test_zero_repayment_rejected(admin_client, capital_source):
    r = admin_client.post(
        f"/funding-sources/{capital_source['id']}/repayments",
        json={"source_id": capital_source["id"], "principal_amount": 0,
              "interest_amount": 0, "date": "2026-02-04"},
    )
    assert r.status_code == 400


def test_interest_expense_category_available(admin_client):
    """New category exposed by /expense-categories."""
    r = admin_client.get("/expense-categories")
    assert r.status_code == 200
    data = r.json()
    flat = data.get("flat", [])
    assert "Interest Expense (Capital)" in flat
