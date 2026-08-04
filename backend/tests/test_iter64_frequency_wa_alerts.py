"""Iter 64 — Payment Frequency (monthly / quarterly / lump_sum) +
Admin WhatsApp Alerts (admin_alerts_phone setting).

Verifies:
- payment_frequency = 'monthly' walks +1 month per anchor
- payment_frequency = 'quarterly' walks +3 months per anchor
- payment_frequency = 'lump_sum' has a single anchor at start + term_months
- admin_alerts_phone is a first-class setting field (roundtrip PUT/GET)
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


def _next_due(s, sid):
    listed = s.get(f"{API}/funding-sources", timeout=15).json()
    return next(x for x in listed if x["id"] == sid)


@pytest.fixture
def source_factory(s):
    created = []

    def make(**kw):
        payload = {
            "name": f"pytest-iter64-{os.getpid()}-{len(created)}",
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


class TestPaymentFrequency:
    def test_monthly_walks_by_one_month(self, s, source_factory):
        src = source_factory(payment_frequency="monthly", start_date="2026-01-01")
        row = _next_due(s, src["id"])
        # next_due must be a monthly anchor from Jan 1, 2026
        nd = date.fromisoformat(row["next_due_date"])
        assert nd.day == 1, f"monthly anchor should fall on day 1: {nd}"

    def test_quarterly_walks_by_three_months(self, s, source_factory):
        src = source_factory(payment_frequency="quarterly", start_date="2026-01-01")
        row = _next_due(s, src["id"])
        nd = date.fromisoformat(row["next_due_date"])
        # 2026-01-01 + N × 3 months → next anchor is 2026-04, 07, 10 or 2027-01
        assert nd.month in {4, 7, 10, 1}, f"quarterly anchor: {nd}"
        assert nd.day == 1

    def test_lump_sum_has_single_anchor_at_end(self, s, source_factory):
        src = source_factory(
            payment_frequency="lump_sum",
            start_date="2026-01-01",
            term_months=6,
        )
        row = _next_due(s, src["id"])
        # lump_sum → next_due = start + term_months = 2026-07-01
        assert row["next_due_date"] == "2026-07-01", row["next_due_date"]


class TestAdminAlertsPhone:
    def test_setting_roundtrip(self, s):
        # PUT
        r = s.put(f"{API}/settings", json={"admin_alerts_phone": "+67078372678"}, timeout=15)
        assert r.status_code == 200, r.text
        # GET
        got = s.get(f"{API}/settings", timeout=15).json()
        assert got["admin_alerts_phone"] == "+67078372678"

    def test_setting_can_be_cleared(self, s):
        r = s.put(f"{API}/settings", json={"admin_alerts_phone": ""}, timeout=15)
        assert r.status_code == 200
        got = s.get(f"{API}/settings", timeout=15).json()
        assert got["admin_alerts_phone"] == ""
