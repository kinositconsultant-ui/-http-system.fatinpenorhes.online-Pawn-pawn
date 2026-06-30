"""Iter13 — Per-user module access permissions tests.

Covers:
- GET /api/users/modules catalog (admin-only, 403 for non-admin)
- POST /api/users with custom allowed_modules / role-defaults / admin force-full
- PATCH /api/users (role/name/password/modules updates, admin auto-lock, bad filter)
- /api/auth/me + /api/auth/login return allowed_modules
- Module gating on /clients /payments /finance /items /contracts /auctions /reports /dashboard
- Admins bypass gating
- Backfill on boot
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"

ALL_MODULES = [
    "dashboard", "clients", "items", "contracts", "payments",
    "auctions", "reports", "finance", "users", "settings", "audit_log",
]
STAFF_DEFAULTS = ["dashboard", "clients", "items", "contracts", "payments", "auctions", "reports"]
CASHIER_DEFAULTS = ["dashboard", "payments"]


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def cashier_data(admin_session):
    """Create a fresh cashier user with explicit modules [dashboard, payments]."""
    ts = int(time.time() * 1000)
    email = f"test_cashier_{ts}@fatinpenhores.tl"
    password = "cashpass123"
    r = admin_session.post(f"{API}/users", json={
        "email": email,
        "password": password,
        "name": "TEST Cashier",
        "role": "cashier",
        "allowed_modules": ["dashboard", "payments"],
    }, timeout=10)
    assert r.status_code == 200, f"cashier create failed: {r.status_code} {r.text}"
    user = r.json()
    yield {"id": user["id"], "email": email, "password": password, "user": user}
    # cleanup
    try:
        admin_session.delete(f"{API}/users/{user['id']}", timeout=5)
    except Exception:
        pass


@pytest.fixture()
def cashier_session(cashier_data):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={
        "email": cashier_data["email"],
        "password": cashier_data["password"],
    }, timeout=10)
    assert r.status_code == 200, f"cashier login failed: {r.text}"
    return s


# ---------- Module catalog endpoint ----------
class TestModulesCatalog:
    def test_admin_gets_catalog(self, admin_session):
        r = admin_session.get(f"{API}/users/modules", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "modules" in data and "role_defaults" in data
        assert set(data["modules"]) == set(ALL_MODULES)
        assert len(data["modules"]) == 11
        assert set(data["role_defaults"]["admin"]) == set(ALL_MODULES)
        assert set(data["role_defaults"]["staff"]) == set(STAFF_DEFAULTS)
        assert set(data["role_defaults"]["cashier"]) == set(CASHIER_DEFAULTS)

    def test_cashier_gets_403(self, cashier_session):
        r = cashier_session.get(f"{API}/users/modules", timeout=10)
        assert r.status_code == 403, r.text


# ---------- User create flows ----------
class TestUserCreate:
    def test_custom_modules_persisted(self, admin_session, cashier_data):
        # Already created via fixture — verify via GET /users
        r = admin_session.get(f"{API}/users", timeout=10)
        assert r.status_code == 200
        found = [u for u in r.json() if u["id"] == cashier_data["id"]]
        assert len(found) == 1
        assert set(found[0]["allowed_modules"]) == {"dashboard", "payments"}

    def test_role_defaults_when_modules_omitted(self, admin_session):
        ts = int(time.time() * 1000)
        email = f"test_staff_default_{ts}@x.com"
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": "p", "name": "TEST Staff", "role": "staff",
        }, timeout=10)
        assert r.status_code == 200, r.text
        u = r.json()
        try:
            assert set(u["allowed_modules"]) == set(STAFF_DEFAULTS)
        finally:
            admin_session.delete(f"{API}/users/{u['id']}")

    def test_admin_role_forces_all_modules(self, admin_session):
        ts = int(time.time() * 1000)
        email = f"test_admin_force_{ts}@x.com"
        # Pass deliberately restricted modules — backend should override.
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": "p", "name": "TEST Admin", "role": "admin",
            "allowed_modules": ["dashboard"],
        }, timeout=10)
        assert r.status_code == 200, r.text
        u = r.json()
        try:
            assert set(u["allowed_modules"]) == set(ALL_MODULES)
        finally:
            admin_session.delete(f"{API}/users/{u['id']}")

    def test_bad_module_names_filtered(self, admin_session):
        ts = int(time.time() * 1000)
        email = f"test_filter_{ts}@x.com"
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": "p", "name": "TEST Filt", "role": "cashier",
            "allowed_modules": ["dashboard", "garbage", "payments", "doesnotexist"],
        }, timeout=10)
        assert r.status_code == 200, r.text
        u = r.json()
        try:
            assert set(u["allowed_modules"]) == {"dashboard", "payments"}
        finally:
            admin_session.delete(f"{API}/users/{u['id']}")


# ---------- User patch flows ----------
class TestUserPatch:
    def test_patch_name_only(self, admin_session, cashier_data):
        r = admin_session.patch(f"{API}/users/{cashier_data['id']}", json={"name": "TEST Cashier Renamed"}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "TEST Cashier Renamed"

    def test_patch_modules_with_invalid_filtered(self, admin_session, cashier_data):
        r = admin_session.patch(f"{API}/users/{cashier_data['id']}", json={
            "allowed_modules": ["dashboard", "payments", "clients", "notarealmodule"],
        }, timeout=10)
        assert r.status_code == 200, r.text
        assert set(r.json()["allowed_modules"]) == {"dashboard", "payments", "clients"}

    def test_patch_to_admin_locks_full_modules(self, admin_session):
        # Create temp staff user, patch role to admin with restricted modules — expect override.
        ts = int(time.time() * 1000)
        email = f"test_promote_{ts}@x.com"
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": "p", "name": "TEST Promote", "role": "staff",
        }, timeout=10)
        uid = r.json()["id"]
        try:
            r2 = admin_session.patch(f"{API}/users/{uid}", json={
                "role": "admin", "allowed_modules": ["dashboard"],
            }, timeout=10)
            assert r2.status_code == 200, r2.text
            data = r2.json()
            assert data["role"] == "admin"
            assert set(data["allowed_modules"]) == set(ALL_MODULES)
        finally:
            admin_session.delete(f"{API}/users/{uid}")

    def test_patch_password(self, admin_session):
        ts = int(time.time() * 1000)
        email = f"test_pwd_{ts}@x.com"
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": "old123", "name": "TEST Pwd", "role": "cashier",
        }, timeout=10)
        uid = r.json()["id"]
        try:
            r2 = admin_session.patch(f"{API}/users/{uid}", json={"password": "new456"}, timeout=10)
            assert r2.status_code == 200
            # try login with new password
            s = requests.Session()
            r3 = s.post(f"{API}/auth/login", json={"email": email, "password": "new456"}, timeout=10)
            assert r3.status_code == 200, "new password should work"
            r4 = requests.Session().post(f"{API}/auth/login", json={"email": email, "password": "old123"}, timeout=10)
            assert r4.status_code == 401, "old password should no longer work"
        finally:
            admin_session.delete(f"{API}/users/{uid}")


# ---------- /auth/me and /auth/login return allowed_modules ----------
class TestAuthShape:
    def test_auth_me_has_allowed_modules_admin(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200, r.text
        u = r.json()
        assert "allowed_modules" in u
        assert set(u["allowed_modules"]) == set(ALL_MODULES)

    def test_auth_login_returns_allowed_modules(self, cashier_data):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={
            "email": cashier_data["email"], "password": cashier_data["password"],
        }, timeout=10)
        assert r.status_code == 200
        data = r.json()
        # Login returns flat user shape (no wrapping "user" key).
        assert "allowed_modules" in data
        assert "dashboard" in data["allowed_modules"]
        assert "payments" in data["allowed_modules"]

    def test_auth_me_has_allowed_modules_cashier(self, cashier_session):
        # NOTE: cashier was patched earlier in TestUserPatch to add "clients"; check at least dashboard+payments
        r = cashier_session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        u = r.json()
        assert "allowed_modules" in u
        assert "dashboard" in u["allowed_modules"]
        assert "payments" in u["allowed_modules"]


# ---------- Module gating (cashier) ----------
class TestModuleGating:
    @pytest.fixture(autouse=True)
    def _reset_cashier_modules(self, admin_session, cashier_data):
        # Reset to baseline before each test in this class so order doesn't matter.
        admin_session.patch(f"{API}/users/{cashier_data['id']}", json={
            "allowed_modules": ["dashboard", "payments"],
        }, timeout=10)
        yield

    def test_dashboard_allowed(self, cashier_session):
        r = cashier_session.get(f"{API}/dashboard/summary", timeout=10)
        assert r.status_code == 200, r.text

    def test_payments_allowed(self, cashier_session):
        r = cashier_session.get(f"{API}/payments", timeout=10)
        assert r.status_code == 200, r.text

    def test_clients_blocked(self, cashier_session):
        r = cashier_session.get(f"{API}/clients", timeout=10)
        assert r.status_code == 403, r.text
        assert "clients" in r.json().get("detail", "").lower()

    def test_finance_blocked(self, cashier_session):
        r = cashier_session.get(f"{API}/finance/summary", timeout=10)
        assert r.status_code == 403, r.text

    def test_items_car_blocked(self, cashier_session):
        r = cashier_session.get(f"{API}/items/car", timeout=10)
        assert r.status_code == 403, r.text

    def test_contracts_blocked(self, cashier_session):
        r = cashier_session.get(f"{API}/contracts", timeout=10)
        assert r.status_code == 403, r.text

    def test_auctions_blocked(self, cashier_session):
        r = cashier_session.get(f"{API}/auctions", timeout=10)
        assert r.status_code == 403, r.text

    def test_reports_blocked(self, cashier_session):
        r = cashier_session.get(f"{API}/reports/v2/inventory", timeout=10)
        assert r.status_code == 403, r.text

    def test_add_clients_then_allowed(self, admin_session, cashier_data, cashier_session):
        # Add clients module via PATCH
        r = admin_session.patch(f"{API}/users/{cashier_data['id']}", json={
            "allowed_modules": ["dashboard", "payments", "clients"],
        }, timeout=10)
        assert r.status_code == 200
        # Need fresh login: the cashier session still has the old token, but require_module
        # reads from DB each request via get_current_user, so existing session should now work.
        r2 = cashier_session.get(f"{API}/clients", timeout=10)
        assert r2.status_code == 200, r2.text


# ---------- Admin never gated ----------
class TestAdminBypass:
    def test_admin_can_hit_all_modules(self, admin_session):
        endpoints = [
            "/clients", "/payments", "/contracts", "/auctions",
            "/dashboard/summary", "/finance/summary",
            "/items/car", "/reports/v2/inventory",
        ]
        for ep in endpoints:
            r = admin_session.get(f"{API}{ep}", timeout=15)
            assert r.status_code == 200, f"admin {ep} -> {r.status_code} {r.text[:200]}"


# ---------- Backfill ----------
class TestBackfill:
    def test_all_existing_users_have_allowed_modules(self, admin_session):
        r = admin_session.get(f"{API}/users", timeout=10)
        assert r.status_code == 200
        users = r.json()
        assert len(users) > 0
        for u in users:
            assert "allowed_modules" in u, f"user {u.get('email')} missing allowed_modules"
            assert isinstance(u["allowed_modules"], list)
            # Must be non-empty AND match role defaults at minimum (or be full for admin)
            if u.get("role") == "admin":
                assert set(u["allowed_modules"]) == set(ALL_MODULES), f"admin {u['email']} not full"
            else:
                assert len(u["allowed_modules"]) > 0, f"non-admin {u['email']} has empty modules"
