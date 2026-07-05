"""Iteration 25 — Auth extras (Remember me + Forgot/Reset password) + Audit log exports.

Verifies:
- Login with remember=true issues a longer-lived refresh cookie (max_age > 7d)
- Login with remember omitted keeps default 7d expiry
- Forgot password always returns generic 200 (email enumeration safe)
- Reset flow: token info → reset → token single-use → cannot login with old pwd
- Admin manual password reset (POST /users/{id}/reset-password)
- Audit log filters + CSV + PDF export return correct content types
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone

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
    assert r.status_code == 200, r.text
    return s


class TestRememberMe:
    def test_remember_true_extends_refresh_cookie(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASS, "remember": True},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        set_cookies = r.headers.get_all("set-cookie") if hasattr(r.headers, "get_all") else [
            v for k, v in r.raw.headers.items() if k.lower() == "set-cookie"
        ]
        # httpx-style fallback
        if not set_cookies:
            set_cookies = [r.headers.get("set-cookie", "")]
        refresh_lines = [c for c in set_cookies if c and "refresh_token=" in c]
        assert refresh_lines, f"No refresh_token cookie in Set-Cookie headers: {set_cookies}"
        joined = " ".join(refresh_lines).lower()
        # 30 days = 2,592,000s. Anything > 604,800s (7d) proves remember worked.
        assert "max-age=2592000" in joined or "max-age=2591" in joined, joined

    def test_default_is_7_days(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},  # no remember
            timeout=15,
        )
        assert r.status_code == 200
        set_cookies = r.headers.get_all("set-cookie") if hasattr(r.headers, "get_all") else []
        if not set_cookies:
            set_cookies = [r.headers.get("set-cookie", "")]
        joined = " ".join(set_cookies).lower()
        # 7d = 604800s
        assert "max-age=604800" in joined or "max-age=6047" in joined, joined


class TestForgotResetFlow:
    def test_full_reset_cycle(self):
        # Create a throwaway test user so we don't disturb admin
        marker = uuid.uuid4().hex[:8]
        temp_email = f"reset_test_{marker}@fatinpenhores.tl"
        admin = requests.Session()
        admin.post(f"{BASE_URL}/api/auth/login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
        u = admin.post(
            f"{BASE_URL}/api/users",
            json={"email": temp_email, "password": "initial1234", "name": "Reset Test", "role": "staff"},
            timeout=15,
        )
        assert u.status_code in (200, 201), u.text
        temp_id = u.json()["id"]

        # 1. Request forgot password
        r = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": temp_email},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # 2. Unknown email also returns 200 (enumeration safe)
        r2 = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": f"nobody-{marker}@nowhere.tl"},
            timeout=15,
        )
        assert r2.status_code == 200

        # 3. Fetch the fresh token directly from Mongo (bypasses email delivery)
        from pymongo import MongoClient
        client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        doc = db.password_reset_tokens.find_one({"email": temp_email, "used_at": None},
                                                 sort=[("created_at", -1)])
        assert doc is not None, "Reset token was not persisted"
        token = doc["token"]

        # 4. reset-token-info returns masked email
        info = requests.get(f"{BASE_URL}/api/auth/reset-token-info?token={token}", timeout=10)
        assert info.status_code == 200
        assert info.json()["email_masked"].startswith("r***")

        # 5. reset-password consumes the token
        rp = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={"token": token, "new_password": "brandnew1234"},
            timeout=15,
        )
        assert rp.status_code == 200

        # 6. Old password no longer works
        bad = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": temp_email, "password": "initial1234"},
            timeout=15,
        )
        assert bad.status_code == 401

        # 7. New password works
        ok = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": temp_email, "password": "brandnew1234"},
            timeout=15,
        )
        assert ok.status_code == 200

        # 8. Token is single-use — reusing yields 410
        reused = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={"token": token, "new_password": "yetanother"},
            timeout=15,
        )
        assert reused.status_code == 410

        # cleanup
        admin.delete(f"{BASE_URL}/api/users/{temp_id}", timeout=10)


class TestAdminManualReset:
    def test_admin_can_reset_user_password(self, api):
        marker = uuid.uuid4().hex[:8]
        email = f"admin_reset_{marker}@fatinpenhores.tl"
        u = api.post(
            f"{BASE_URL}/api/users",
            json={"email": email, "password": "original1234", "name": "Admin Reset", "role": "cashier"},
            timeout=15,
        )
        assert u.status_code in (200, 201), u.text
        uid = u.json()["id"]

        rr = api.post(
            f"{BASE_URL}/api/users/{uid}/reset-password",
            json={"new_password": "forceset1234"},
            timeout=15,
        )
        assert rr.status_code == 200, rr.text

        # Login with new password works
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": "forceset1234"},
            timeout=15,
        )
        assert r.status_code == 200

        # Non-admin cannot call the endpoint
        cashier = requests.Session()
        cashier.post(f"{BASE_URL}/api/auth/login",
                     json={"email": email, "password": "forceset1234"}, timeout=15)
        forbidden = cashier.post(
            f"{BASE_URL}/api/users/{uid}/reset-password",
            json={"new_password": "hackme12345"},
            timeout=10,
        )
        assert forbidden.status_code in (401, 403)

        api.delete(f"{BASE_URL}/api/users/{uid}", timeout=10)


class TestAuditLogExports:
    def test_filter_by_action(self, api):
        r = api.get(f"{BASE_URL}/api/audit-log?action=update&limit=5", timeout=15)
        assert r.status_code == 200
        for row in r.json():
            assert row["action"] == "update"

    def test_filter_by_actor_email_partial(self, api):
        r = api.get(f"{BASE_URL}/api/audit-log?actor_email=admin&limit=5", timeout=15)
        assert r.status_code == 200
        for row in r.json():
            assert "admin" in (row.get("actor_email") or "").lower()

    def test_csv_export(self, api):
        r = api.get(f"{BASE_URL}/api/audit-log/export/csv?limit=10", timeout=15)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        body = r.text.splitlines()
        assert body[0].startswith("created_at,")

    def test_pdf_export(self, api):
        r = api.get(f"{BASE_URL}/api/audit-log/export/pdf?limit=5", timeout=15)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 2000  # branded PDF is at least a few KB
