"""Iteration 30 — Reminder scheduler + Rule A math end-to-end integration.

Verifies:
1. Admin can trigger a manual reminder run via POST /api/reminders/run and
   receives a summary dict with scanned/sent/skipped/errors fields.
2. Rule A math is exposed on GET /api/contracts/{id}: creating a contract with
   contract_date=today-32 days, loan=$500, rate=10% yields months_elapsed=2,
   interest_amount=$100, per_month_interest=$50.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASS = "admin123"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


# ---------- Manual reminder run ----------
class TestReminderRun:
    def test_run_reminders_endpoint_returns_summary(self, api):
        r = api.post(f"{BASE_URL}/api/reminders/run", timeout=30)
        assert r.status_code == 200, f"unexpected status: {r.status_code} {r.text}"
        data = r.json()
        # Expected summary shape from reminders.run_daily_reminders
        for key in ("scanned", "sent", "skipped", "errors"):
            assert key in data, f"missing key '{key}' in response: {data}"
        assert isinstance(data["scanned"], int)
        assert isinstance(data["sent"], int)
        assert isinstance(data["skipped"], int)
        assert isinstance(data["errors"], int)

    def test_run_reminders_forbidden_without_admin(self):
        # Unauth (no cookie) → 401
        r = requests.post(f"{BASE_URL}/api/reminders/run", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Rule A math E2E via API ----------
class TestRuleAMathE2E:
    def test_contract_shows_rule_a_math_at_32_days(self, api):
        # Seed: client + car item
        marker = uuid.uuid4().hex[:8]
        client_payload = {
            "full_name": f"TEST_RuleA_{marker}",
            "phone": "+67078000000",
            "address": "Dili",
            "id_type": "BI",
            "id_number": f"TEST{marker}",
        }
        rc = api.post(f"{BASE_URL}/api/clients", json=client_payload, timeout=15)
        assert rc.status_code in (200, 201), rc.text
        client_id = rc.json()["id"]

        car_payload = {
            "name": f"TEST Toyota Hilux {marker}",
            "brand": "Toyota",
            "model": "Hilux",
            "manufacture_year": 2018,
            "plate": f"TST-{marker[:4]}",
            "color": "White",
            "market_value": 5000,
        }
        ri = api.post(f"{BASE_URL}/api/items/car", json=car_payload, timeout=15)
        assert ri.status_code in (200, 201), ri.text
        item_id = ri.json()["id"]

        # Backdated 32 days: past Aug-11 anniversary by ~2 days → months_elapsed=2 (Rule A)
        contract_date = (date.today() - timedelta(days=32)).isoformat()
        # Term = 1 month so due_date < today (contract may be overdue, no problem for GET)
        due_date = (date.today() - timedelta(days=2)).isoformat()
        contract_payload = {
            "client_id": client_id,
            "item_id": item_id,
            "item_type": "car",
            "loan_amount": 500,
            "interest_rate": 10,
            "contract_date": contract_date,
            "due_date": due_date,
            "notes": f"TEST_iter30_{marker}",
        }
        cr = api.post(f"{BASE_URL}/api/contracts", json=contract_payload, timeout=15)
        assert cr.status_code in (200, 201), cr.text
        contract = cr.json()
        contract_id = contract["id"]

        # GET to verify computed Rule A math is exposed
        gr = api.get(f"{BASE_URL}/api/contracts/{contract_id}", timeout=15)
        assert gr.status_code == 200, gr.text
        data = gr.json()

        assert data["months_elapsed"] == 2, (
            f"Rule A: expected months_elapsed=2 for a 32-day-old contract, "
            f"got {data['months_elapsed']}"
        )
        assert float(data["per_month_interest"]) == 50.0, data
        assert float(data["interest_amount"]) == 100.0, data
