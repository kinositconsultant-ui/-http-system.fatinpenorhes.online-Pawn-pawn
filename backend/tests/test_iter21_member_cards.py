"""Iteration 21 — Member ID Card lifecycle.

Covers:
- Issue: assigns member_no (FP-YYYY-####), status=active, 1-year expiry, verify_token.
- Re-issue is idempotent (same member_no).
- PDF endpoint returns a real PDF byte-stream.
- Public /verify/{token} endpoint requires no auth and returns correct status.
- Revoke sets status=revoked and public verify returns valid=false.
- Renew re-activates and pushes expiry +1 year.
- RBAC: cashier cannot issue; only admin can revoke.
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def cashier(admin):
    email = f"TEST_cashier_iter21_{int(time.time())}@fatinpenhores.tl"
    password = "cashier123"
    r = admin.post(f"{API}/users", json={
        "name": "Cashier Iter21", "email": email, "password": password,
        "role": "cashier", "allowed_modules": ["dashboard", "payments"],
    }, timeout=15)
    if r.status_code not in (200, 201):
        pytest.skip(f"cashier user create failed: {r.status_code} {r.text[:200]}")
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"cashier login failed: {r.status_code}")
    return s


@pytest.fixture(scope="module")
def client_id(admin):
    """Create a dedicated client for card tests."""
    ts = int(time.time())
    payload = {
        "full_name": f"TEST_MemberCard_{ts}",
        "id_type": "BI",
        "id_number": f"MC-{ts}",
        "phone": "+670 7000 0000",
        "address": "Test", "municipality": "Dili",
        "posto": "Nain Feto", "suco": "Caicoli", "aldeia": "Test",
    }
    r = admin.post(f"{API}/clients", json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    yield cid
    # cleanup
    admin.delete(f"{API}/clients/{cid}", timeout=10)


class TestMemberCardLifecycle:
    def test_issue_card(self, admin, client_id):
        r = admin.post(f"{API}/clients/{client_id}/issue-card", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("member_no", "").startswith("FP-"), body
        assert body["member_status"] == "active"
        assert body["member_issued_at"] == date.today().isoformat()
        # Expires 1 year later (365 days)
        exp = date.fromisoformat(body["member_expires_at"])
        assert (exp - date.today()).days == 365
        assert len(body["member_verify_token"]) >= 16
        # stash for later tests
        TestMemberCardLifecycle.token = body["member_verify_token"]
        TestMemberCardLifecycle.member_no = body["member_no"]

    def test_reissue_idempotent(self, admin, client_id):
        r = admin.post(f"{API}/clients/{client_id}/issue-card", timeout=15)
        assert r.status_code == 200
        assert r.json()["member_no"] == TestMemberCardLifecycle.member_no
        assert r.json()["member_verify_token"] == TestMemberCardLifecycle.token

    def test_card_pdf_generation(self, admin, client_id):
        r = admin.get(f"{API}/clients/{client_id}/card-pdf", timeout=20)
        assert r.status_code == 200, r.text[:200]
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-", "not a PDF"
        assert len(r.content) > 3000  # non-empty realistic PDF

    def test_public_verify_active(self, client_id):
        # Public endpoint — NO auth cookie needed
        s = requests.Session()
        r = s.get(f"{API}/public/verify/{TestMemberCardLifecycle.token}", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is True
        assert body["status"] == "active"
        assert body["member_no"] == TestMemberCardLifecycle.member_no

    def test_public_verify_bad_token(self):
        s = requests.Session()
        r = s.get(f"{API}/public/verify/thisisdefinitelynotarealtoken", timeout=15)
        assert r.status_code == 200
        assert r.json() == {"valid": False, "status": "not_found"}

    def test_public_verify_too_short(self):
        s = requests.Session()
        r = s.get(f"{API}/public/verify/xx", timeout=15)
        # too-short token → 404
        assert r.status_code == 404

    def test_revoke_and_verify(self, admin, client_id):
        r = admin.post(f"{API}/clients/{client_id}/revoke-card", timeout=15)
        assert r.status_code == 200
        assert r.json()["member_status"] == "revoked"

        s = requests.Session()
        r = s.get(f"{API}/public/verify/{TestMemberCardLifecycle.token}", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is False
        assert body["status"] == "revoked"

    def test_renew_reactivates(self, admin, client_id):
        r = admin.post(f"{API}/clients/{client_id}/renew-card", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["member_status"] == "active"
        assert body["member_issued_at"] == date.today().isoformat()

        s = requests.Session()
        r = s.get(f"{API}/public/verify/{TestMemberCardLifecycle.token}", timeout=15)
        assert r.json()["valid"] is True


class TestRBAC:
    def test_cashier_cannot_issue(self, cashier, client_id):
        r = cashier.post(f"{API}/clients/{client_id}/issue-card", timeout=15)
        assert r.status_code in (401, 403), f"cashier should be blocked but got {r.status_code}"

    def test_cashier_cannot_revoke(self, cashier, client_id):
        r = cashier.post(f"{API}/clients/{client_id}/revoke-card", timeout=15)
        assert r.status_code in (401, 403)
