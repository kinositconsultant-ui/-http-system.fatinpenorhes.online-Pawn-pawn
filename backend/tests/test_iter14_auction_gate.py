"""Iter14 — Public auction gating + shared warehouse token tests."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"
VISITOR_PASSWORD = "visitor42"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session", autouse=True)
def ensure_visitor_password(admin_session):
    """Make sure warehouse_password is set to visitor42 for these tests."""
    r = admin_session.put(f"{API}/settings", json={"warehouse_password": VISITOR_PASSWORD}, timeout=10)
    assert r.status_code == 200, r.text
    yield


class TestAuctionStatus:
    def test_status_locked_when_password_set(self):
        r = requests.get(f"{API}/public/auction-status", timeout=10)
        assert r.status_code == 200
        assert r.json()["locked"] is True


class TestAuctionGate:
    def test_no_token_returns_401(self):
        r = requests.get(f"{API}/public/auction-items", timeout=10)
        assert r.status_code == 401
        assert "lock" in r.json().get("detail", "").lower()

    def test_bad_token_returns_401(self):
        r = requests.get(f"{API}/public/auction-items", params={"unlock_token": "garbage.token.xxx"}, timeout=10)
        assert r.status_code == 401

    def test_unlock_with_visitor_password(self):
        r = requests.post(f"{API}/public/warehouse-unlock", json={"password": VISITOR_PASSWORD}, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("token")

    def test_unlock_with_bad_password(self):
        r = requests.post(f"{API}/public/warehouse-unlock", json={"password": "wrongpass"}, timeout=10)
        assert r.status_code == 401

    def test_token_unlocks_auction_items(self):
        r = requests.post(f"{API}/public/warehouse-unlock", json={"password": VISITOR_PASSWORD}, timeout=10)
        token = r.json()["token"]
        r2 = requests.get(f"{API}/public/auction-items", params={"unlock_token": token}, timeout=10)
        assert r2.status_code == 200, r2.text
        items = r2.json()
        assert isinstance(items, list)
        # Each item should have expected keys
        for it in items[:3]:
            assert "id" in it
            assert "item_type" in it

    def test_same_token_unlocks_warehouse(self):
        """Shared visitor token: same token should also unlock /public/warehouse."""
        r = requests.post(f"{API}/public/warehouse-unlock", json={"password": VISITOR_PASSWORD}, timeout=10)
        token = r.json()["token"]
        r2 = requests.get(f"{API}/public/warehouse", params={"unlock_token": token}, timeout=10)
        assert r2.status_code == 200, r2.text
