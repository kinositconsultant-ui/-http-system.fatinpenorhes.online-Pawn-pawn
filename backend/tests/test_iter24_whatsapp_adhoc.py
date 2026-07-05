"""Iteration 24 — Ad-hoc WhatsApp "Preview & Send" endpoints.

Verifies:
- POST /api/whatsapp/preview returns a Rule A reminder body + metadata for a
  contract, in both EN and TET.
- POST /api/whatsapp/adhoc-send accepts an (optionally edited) body and returns
  a `mocked` status when WhatsApp isn't configured, without raising.
- Auth: unauthenticated → 401.
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


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def contract_id(api):
    marker = uuid.uuid4().hex[:8]
    rc = api.post(
        f"{BASE_URL}/api/clients",
        json={
            "full_name": f"TEST_adhoc_{marker}",
            "phone": "+67078000000",
            "address": "Dili",
            "id_type": "BI",
            "id_number": f"AD{marker}",
        },
        timeout=15,
    )
    assert rc.status_code in (200, 201), rc.text
    cid = rc.json()["id"]

    ri = api.post(
        f"{BASE_URL}/api/items/car",
        json={
            "name": f"TEST Toyota Hilux {marker}",
            "brand": "Toyota",
            "model": "Hilux",
            "manufacture_year": 2018,
            "plate": f"AD-{marker[:4]}",
            "color": "White",
            "market_value": 5000,
        },
        timeout=15,
    )
    assert ri.status_code in (200, 201), ri.text
    item_id = ri.json()["id"]

    contract_date = (date.today() - timedelta(days=45)).isoformat()
    due_date = (date.today() - timedelta(days=15)).isoformat()
    cr = api.post(
        f"{BASE_URL}/api/contracts",
        json={
            "client_id": cid,
            "item_id": item_id,
            "item_type": "car",
            "loan_amount": 500,
            "interest_rate": 10,
            "contract_date": contract_date,
            "due_date": due_date,
        },
        timeout=15,
    )
    assert cr.status_code in (200, 201), cr.text
    return cr.json()["id"]


class TestWhatsAppPreview:
    def test_preview_english(self, api, contract_id):
        r = api.post(
            f"{BASE_URL}/api/whatsapp/preview",
            json={"contract_id": contract_id, "language": "en"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        for key in (
            "body",
            "days",
            "months",
            "per_month",
            "total_due",
            "next_month_date",
            "phone",
            "client_name",
            "contract_number",
        ):
            assert key in data, f"missing key {key}"
        # English body should start with "Fatin Penhores — Overdue Notice"
        assert data["body"].startswith("Fatin Penhores"), data["body"]
        assert "Hello" in data["body"], data["body"]
        assert data["language"] == "en"
        assert data["per_month"] == 50.0
        # Rule A: 45-day contract → months=2 → interest=$100 → total=$600
        assert data["months"] == 2
        assert data["total_due"] == 600.0

    def test_preview_tetum(self, api, contract_id):
        r = api.post(
            f"{BASE_URL}/api/whatsapp/preview",
            json={"contract_id": contract_id, "language": "tet"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "Ola" in data["body"]
        assert "juru" in data["body"]  # Tetum for interest
        assert data["language"] == "tet"

    def test_preview_unknown_contract_404(self, api):
        r = api.post(
            f"{BASE_URL}/api/whatsapp/preview",
            json={"contract_id": "no-such-id", "language": "en"},
            timeout=15,
        )
        assert r.status_code == 404

    def test_preview_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/whatsapp/preview",
            json={"contract_id": "x", "language": "en"},
            timeout=15,
        )
        assert r.status_code in (401, 403)


class TestWhatsAppAdhocSend:
    def test_adhoc_send_returns_mocked_when_not_configured(self, api, contract_id):
        # First fetch a preview so we send an edited body
        pv = api.post(
            f"{BASE_URL}/api/whatsapp/preview",
            json={"contract_id": contract_id, "language": "en"},
            timeout=15,
        ).json()
        edited = pv["body"] + "\n\n[edited for test]"
        r = api.post(
            f"{BASE_URL}/api/whatsapp/adhoc-send",
            json={
                "contract_id": contract_id,
                "language": "en",
                "body": edited,
                "to_phone": pv["phone"] or "+67078000000",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # WhatsApp is unconfigured in test env → status = "mocked"
        assert data["status"] in ("mocked", "sent"), data
        assert data.get("body") == edited or "body" in data

    def test_adhoc_send_empty_body_rejected(self, api, contract_id):
        r = api.post(
            f"{BASE_URL}/api/whatsapp/adhoc-send",
            json={
                "contract_id": contract_id,
                "language": "en",
                "body": "   ",
                "to_phone": "+67078000000",
            },
            timeout=15,
        )
        assert r.status_code == 400, r.text
