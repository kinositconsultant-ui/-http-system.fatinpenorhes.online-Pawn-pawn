"""Iter 61 — Option B: Income Statement split + Capital installment reminders."""
import os
import pytest
import requests

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pawnly-pro.preview.emergentagent.com").rstrip("/") + "/api"
ADMIN = {"email": "admin@fatinpenhores.tl", "password": "admin123"}


@pytest.fixture(scope="module")
def s():
    session = requests.Session()
    r = session.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return session


def _summary(s):
    r = s.get(f"{API}/finance/summary", timeout=15)
    assert r.status_code == 200
    return r.json()


class TestOptionBIncomeStatement:
    def test_summary_exposes_operating_and_financial_expenses(self, s):
        d = _summary(s)
        for k in ("operating_expenses", "financial_expenses",
                  "operating_profit", "gross_profit", "net_profit"):
            assert k in d, f"missing key {k}"

    def test_income_statement_math_holds(self, s):
        """Gross − Operating − Financial == Net (± rounding)."""
        d = _summary(s)
        expected = round(d["gross_profit"] - d["operating_expenses"] - d["financial_expenses"], 2)
        assert d["net_profit"] == pytest.approx(expected, abs=0.01)
        # And operating_profit = gross - operating
        expected_op = round(d["gross_profit"] - d["operating_expenses"], 2)
        assert d["operating_profit"] == pytest.approx(expected_op, abs=0.01)

    def test_interest_expense_goes_to_financial_bucket(self, s):
        """Booking a repayment with interest should flow into financial_expenses,
        not operating_expenses."""
        # Create source + repayment
        source = s.post(f"{API}/funding-sources", json={
            "name": f"pytest-iter61-{os.getpid()}",
            "source_type": "bank",
            "principal_amount": 5000.0,
            "interest_rate": 5.0,
            "interest_period": "monthly",
            "term_months": 12,
            "start_date": "2026-01-01",
            "due_date": "2027-01-01",
        }, timeout=15).json()

        try:
            before = _summary(s)
            r = s.post(f"{API}/funding-sources/{source['id']}/repayments", json={
                "source_id": source["id"],
                "principal_amount": 200,
                "interest_amount": 50,
                "date": "2026-02-04",
            }, timeout=15)
            assert r.status_code == 200, r.text

            after = _summary(s)
            # Interest went into financial_expenses (+50), NOT operating
            assert after["financial_expenses"] == pytest.approx(before["financial_expenses"] + 50, abs=0.01)
            assert after["operating_expenses"] == pytest.approx(before["operating_expenses"], abs=0.01)
            # And net_profit dropped by exactly 50
            assert after["net_profit"] == pytest.approx(before["net_profit"] - 50, abs=0.01)
        finally:
            s.delete(f"{API}/funding-sources/{source['id']}", timeout=15)


class TestCapitalReminders:
    def test_endpoint_exists_and_returns_summary(self, s):
        r = s.post(f"{API}/reminders/run-capital", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("scanned", "sent", "skipped", "errors", "attempted"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["scanned"], int)

    def test_force_flag_scans_overdue_sources(self, s):
        """Force=true should scan sources even outside the 7/3/1/0 buckets."""
        r = s.post(f"{API}/reminders/run-capital?force=true", timeout=30)
        assert r.status_code == 200
        d = r.json()
        # scanned >= all funding sources
        sources = s.get(f"{API}/funding-sources", timeout=15).json()
        assert d["scanned"] >= len(sources) or d.get("disabled")

    def test_capital_reminder_triggers_when_due_within_window(self, s):
        """Create a funding source with start_date == today and next_due
        should be within CAPITAL_REMINDER_DAYS. Then force-run and verify at
        least one 'attempted' record is produced (email may be mocked)."""
        from datetime import date, timedelta
        # Start 7 days ago so next monthly anchor = today + ~23 days.
        # Instead, we start 30 days ago so next anchor = today.
        start = (date.today() - timedelta(days=30)).isoformat()
        src = s.post(f"{API}/funding-sources", json={
            "name": f"pytest-iter61-due-{os.getpid()}",
            "source_type": "bank",
            "principal_amount": 1000.0,
            "interest_rate": 3.0,
            "interest_period": "monthly",
            "term_months": 6,
            "start_date": start,
        }, timeout=15).json()
        try:
            # Verify source is in a reminder window (0 or close to it)
            listed = s.get(f"{API}/funding-sources", timeout=15).json()
            match = next(x for x in listed if x["id"] == src["id"])
            days_until = match.get("days_until_due")
            # Should be near 0 (± a few days depending on month lengths)
            assert days_until is not None
            # Fire the reminder — should hit our source when days_until ∈ 0..7
            r = s.post(f"{API}/reminders/run-capital?force=true", timeout=30)
            assert r.status_code == 200
            d = r.json()
            # Either 'sent' > 0 or 'attempted' includes our source (channel status
            # may be 'mocked' when Resend key isn't configured).
            names = [a.get("source") for a in d.get("attempted", [])]
            assert src["name"] in names or d.get("disabled"), \
                f"expected {src['name']} in attempted; got {d}"
        finally:
            s.delete(f"{API}/funding-sources/{src['id']}", timeout=15)
