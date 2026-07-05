"""Iter29 integration — Rule A (strict calendar month + 1 grace day) end-to-end.

Creates fresh clients + car items + contracts via the public API and asserts
that GET /api/contracts/{id} returns Rule-A-compliant math.

Rule A examples:
    contract_date = 2026-07-10, due_date = 2026-08-10, loan=500, rate=10
    → months_elapsed = 1, per_month_interest = 50, interest_amount = 50, total_due = 550

    contract_date = 2026-07-10, due_date = 2026-08-11 (one day past anniv)
    → months_elapsed = 2, interest_amount = 100, total_due = 600
"""
from __future__ import annotations

import os
import time
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def client_id(admin):
    ts = int(time.time())
    r = admin.post(f"{BASE_URL}/api/clients", json={
        "full_name": f"TEST Iter29 Client {ts}",
        "id_type": "BI",
        "id_number": f"TEST{ts}",
        "phone": "670-00000000",
    }, timeout=15)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _make_car_item(admin) -> str:
    """Create a fresh unique car item and return its id."""
    ts = int(time.time() * 1000)
    r = admin.post(f"{BASE_URL}/api/items/car", json={
        "brand": "TESTBRAND",
        "model": f"TESTMODEL_{ts}",
        "plate": f"TT-{ts % 100000}",
        "chassis": f"CH{ts}",
        "market_value": 5000,
    }, timeout=15)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _create_contract(admin, client_id, item_id, contract_date, due_date):
    payload = {
        "client_id": client_id,
        "item_id": item_id,
        "item_type": "car",
        "loan_amount": 500,
        "interest_rate": 10,
        "contract_date": contract_date,
        "due_date": due_date,
        "notes": "TEST_iter29",
    }
    r = admin.post(f"{BASE_URL}/api/contracts", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"contract create failed: {r.status_code} {r.text}"
    return r.json()


class TestRuleAContractComputation:
    def test_contract_anniversary_same_month(self, admin, client_id):
        """Jul 10 → Aug 10 = 1 month; loan 500 × 10% = $50 per month."""
        item_id = _make_car_item(admin)
        c0 = _create_contract(admin, client_id, item_id, "2026-07-10", "2026-08-10")
        cid = c0["id"]

        r2 = admin.get(f"{BASE_URL}/api/contracts/{cid}", timeout=15)
        assert r2.status_code == 200, r2.text
        c = r2.json()

        assert c["per_month_interest"] == 50.0, c
        assert c["months_elapsed"] == 1, c
        assert c["interest_amount"] == 50.0, c
        # For this future-dated contract (2026-07-10), today < due_date → no penalty
        if date.today() < date.fromisoformat("2026-08-10"):
            assert c["total_due"] == 550.0, c
            assert c["penalty_full"] == 0.0, c

    def test_contract_one_day_past_anniversary(self, admin, client_id):
        """Jul 10 → Aug 11 = 2 months under Rule A."""
        item_id = _make_car_item(admin)
        c0 = _create_contract(admin, client_id, item_id, "2026-07-10", "2026-08-11")
        cid = c0["id"]

        r2 = admin.get(f"{BASE_URL}/api/contracts/{cid}", timeout=15)
        assert r2.status_code == 200, r2.text
        c = r2.json()

        assert c["per_month_interest"] == 50.0, c
        assert c["months_elapsed"] == 2, c
        assert c["interest_amount"] == 100.0, c
        if date.today() < date.fromisoformat("2026-08-11"):
            assert c["total_due"] == 600.0, c

    def test_next_interest_date_is_future(self, admin, client_id):
        """next_interest_date must be strictly in the future."""
        item_id = _make_car_item(admin)
        c0 = _create_contract(admin, client_id, item_id, "2026-07-10", "2026-08-10")
        cid = c0["id"]

        r2 = admin.get(f"{BASE_URL}/api/contracts/{cid}", timeout=15)
        c = r2.json()

        n = date.fromisoformat(c["next_interest_date"])
        assert n > date.today(), f"next_interest_date {n} must be strictly future"

    def test_recompute_idempotent(self, admin, client_id):
        """Repeated GETs must return identical Rule A fields."""
        item_id = _make_car_item(admin)
        c0 = _create_contract(admin, client_id, item_id, "2026-07-10", "2026-08-10")
        cid = c0["id"]

        a = admin.get(f"{BASE_URL}/api/contracts/{cid}", timeout=15).json()
        b = admin.get(f"{BASE_URL}/api/contracts/{cid}", timeout=15).json()
        for k in ("months_elapsed", "per_month_interest", "interest_amount",
                  "next_interest_date", "total_due"):
            assert a[k] == b[k], f"non-idempotent for {k}: {a[k]} vs {b[k]}"

    def test_two_month_anniversary(self, admin, client_id):
        """Jul 10 → Sep 10 = 2 months (2nd anniversary, not yet 3rd)."""
        item_id = _make_car_item(admin)
        c0 = _create_contract(admin, client_id, item_id, "2026-07-10", "2026-09-10")
        cid = c0["id"]

        c = admin.get(f"{BASE_URL}/api/contracts/{cid}", timeout=15).json()
        assert c["months_elapsed"] == 2, c
        assert c["interest_amount"] == 100.0, c

    # Note: contracts are capped at a 2-month term by the API, so 3+ month
    # scenarios can't be created via HTTP. Those are covered by
    # test_iter22_interest_rule.py unit tests directly on `_months_billed`.
