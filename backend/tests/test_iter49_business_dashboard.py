"""Backend tests for iteration 49 — Business Dashboard endpoints.

Covers:
1. GET /api/business/metrics — returns owner-focused KPIs + per-loan list
2. GET /api/business/cashflow-forecast — 30 consecutive day buckets
3. reminders.REMINDER_DAYS now includes 1 (grace-period day-1 alert)
4. Regression: /api/dashboard/summary, /api/dashboard/trends, /api/dashboard/snapshot/pdf
"""
import os
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.text}"
    return s


# ---------------------------------------------------------------------------
# 1. /api/business/metrics
# ---------------------------------------------------------------------------
class TestBusinessMetrics:
    def test_status_ok(self, admin_session):
        r = admin_session.get(f"{API}/business/metrics")
        assert r.status_code == 200, r.text

    def test_shape_and_types(self, admin_session):
        data = admin_session.get(f"{API}/business/metrics").json()
        # required keys present
        for k in (
            "total_loaned_out",
            "interest_earned_ytd",
            "projected_interest_30d",
            "potential_loss",
            "grace_period_count",
            "auction_ready_count",
            "per_loan",
        ):
            assert k in data, f"missing key: {k}"
        # numeric checks
        for k in (
            "total_loaned_out",
            "interest_earned_ytd",
            "projected_interest_30d",
            "potential_loss",
        ):
            assert isinstance(data[k], (int, float)), f"{k} not numeric"
            assert data[k] >= 0, f"{k} must be >= 0"
        # counts
        assert isinstance(data["grace_period_count"], int)
        assert isinstance(data["auction_ready_count"], int)
        assert data["grace_period_count"] >= 0
        assert data["auction_ready_count"] >= 0
        # per_loan is a list; can be empty on a fresh env but expected to have rows here
        assert isinstance(data["per_loan"], list)

    def test_per_loan_row_shape(self, admin_session):
        data = admin_session.get(f"{API}/business/metrics").json()
        rows = data["per_loan"]
        if not rows:
            pytest.skip("no active loans in system — cannot verify row shape")
        row = rows[0]
        for k in (
            "contract_id",
            "contract_number",
            "client_id",
            "item_type",
            "principal_remaining",
            "interest_rate",
            "interest_earned",
            "interest_projected_30d",
            "status",
            "days_overdue",
            "due_date",
            "client_name",
        ):
            assert k in row, f"missing per_loan key: {k}"
        assert row["status"] in ("active", "overdue", "auction_ready")
        # per_loan sorted by principal desc
        principals = [r["principal_remaining"] for r in rows]
        assert principals == sorted(principals, reverse=True), "per_loan not sorted desc"

    def test_grace_count_matches_overdue_contracts(self, admin_session):
        """grace_period_count should equal contracts with status='overdue'."""
        metrics = admin_session.get(f"{API}/business/metrics").json()
        contracts = admin_session.get(f"{API}/contracts").json()
        overdue = [c for c in contracts if c.get("status") == "overdue"]
        assert metrics["grace_period_count"] == len(overdue), (
            f"grace_period_count={metrics['grace_period_count']} vs overdue contracts={len(overdue)}"
        )

    def test_auction_ready_count_matches_contracts(self, admin_session):
        metrics = admin_session.get(f"{API}/business/metrics").json()
        contracts = admin_session.get(f"{API}/contracts").json()
        ar = [c for c in contracts if c.get("status") == "auction_ready"]
        assert metrics["auction_ready_count"] == len(ar)

    def test_totals_consistency(self, admin_session):
        """total_loaned_out should equal sum of per_loan principals (top 50 is fine
        because we cap at 50, but at least the reported sum >= sum of visible rows)."""
        data = admin_session.get(f"{API}/business/metrics").json()
        rows_sum = sum(r["principal_remaining"] for r in data["per_loan"])
        # total_loaned_out includes ALL active/overdue/auction_ready — could be >= rows_sum
        assert data["total_loaned_out"] + 0.01 >= rows_sum, (
            f"total_loaned_out={data['total_loaned_out']} < per_loan sum={rows_sum}"
        )


# ---------------------------------------------------------------------------
# 2. /api/business/cashflow-forecast
# ---------------------------------------------------------------------------
class TestCashflowForecast:
    def test_status_ok(self, admin_session):
        r = admin_session.get(f"{API}/business/cashflow-forecast")
        assert r.status_code == 200, r.text

    def test_30_consecutive_days_starting_today(self, admin_session):
        data = admin_session.get(f"{API}/business/cashflow-forecast").json()
        assert "days" in data and "total_expected_in" in data
        days = data["days"]
        assert len(days) == 30, f"expected 30 days, got {len(days)}"
        today = date.today()
        for i, d in enumerate(days):
            expected_date = (today + timedelta(days=i)).isoformat()
            assert d["date"] == expected_date, f"day[{i}] date {d['date']} != {expected_date}"

    def test_expected_in_non_negative(self, admin_session):
        data = admin_session.get(f"{API}/business/cashflow-forecast").json()
        for d in data["days"]:
            assert d["expected_in"] >= 0, f"negative expected_in for {d['date']}"
            assert isinstance(d["contract_count"], int)
            assert d["contract_count"] >= 0

    def test_total_matches_day_sum(self, admin_session):
        data = admin_session.get(f"{API}/business/cashflow-forecast").json()
        day_sum = round(sum(d["expected_in"] for d in data["days"]), 2)
        assert abs(day_sum - data["total_expected_in"]) < 0.02, (
            f"total_expected_in={data['total_expected_in']} != sum={day_sum}"
        )


# ---------------------------------------------------------------------------
# 3. reminders.REMINDER_DAYS
# ---------------------------------------------------------------------------
class TestReminderDays:
    def test_reminder_days_include_day_1(self):
        # Parse the constant directly from the source file to avoid importing
        # the `reminders` module (which requires MONGO_URL at import time).
        import re
        with open("/app/backend/reminders.py", "r", encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"^REMINDER_DAYS\s*=\s*\[([^\]]+)\]", src, re.MULTILINE)
        assert m, "REMINDER_DAYS not found in reminders.py"
        days = [int(x.strip()) for x in m.group(1).split(",") if x.strip()]
        assert 1 in days, f"REMINDER_DAYS missing day 1: {days}"
        assert 7 in days
        assert 9 in days
        assert days == [1, 7, 9], f"unexpected REMINDER_DAYS: {days}"


# ---------------------------------------------------------------------------
# 4. Regression — existing dashboard endpoints
# ---------------------------------------------------------------------------
class TestDashboardRegression:
    def test_dashboard_summary(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/summary")
        assert r.status_code == 200, r.text
        data = r.json()
        # Must still return the core counts used by /dashboard page
        assert isinstance(data, dict) and len(data) > 0

    def test_dashboard_trends(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/trends")
        assert r.status_code == 200, r.text

    def test_dashboard_snapshot_pdf(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/snapshot/pdf")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 500, "PDF too small — likely broken"


# ---------------------------------------------------------------------------
# 5. Auth guard — /business/* must require login
# ---------------------------------------------------------------------------
class TestBusinessAuth:
    def test_metrics_requires_auth(self):
        r = requests.get(f"{API}/business/metrics")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_cashflow_requires_auth(self):
        r = requests.get(f"{API}/business/cashflow-forecast")
        assert r.status_code in (401, 403)
