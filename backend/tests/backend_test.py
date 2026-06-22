"""End-to-end backend tests for Fatin Penhores Pawn System.

Covers: auth, users, clients, items (car/motorcycle/electronic), contracts,
payments, auctions, reports, dashboard, public endpoints, authorization.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://pawnly-pro.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# -------- Fixtures --------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["role"] == "admin"
    return s


@pytest.fixture(scope="session")
def staff_session(admin_session):
    """Create a staff user via admin, return a session logged in as that staff."""
    email = f"TEST_staff_{uuid.uuid4().hex[:6]}@fatinpenhores.tl"
    password = "staffpass123"
    r = admin_session.post(f"{API}/users", json={
        "email": email, "password": password, "name": "Test Staff", "role": "staff"
    })
    assert r.status_code == 200, r.text
    s = requests.Session()
    r2 = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200, r2.text
    s.staff_id = r.json()["id"]
    return s


# -------- Health --------
def test_health_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# -------- Auth --------
class TestAuth:
    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_authenticated(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == ADMIN_EMAIL
        assert body["role"] == "admin"

    def test_login_sets_httponly_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        # Cookie must be present
        names = {c.name for c in s.cookies}
        assert "access_token" in names
        assert "refresh_token" in names

    def test_refresh(self, admin_session):
        r = admin_session.post(f"{API}/auth/refresh")
        assert r.status_code == 200

    def test_logout(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # After logout, /auth/me should be 401
        r2 = s.get(f"{API}/auth/me")
        assert r2.status_code == 401


# -------- Users --------
class TestUsers:
    def test_list_users_requires_admin(self):
        r = requests.get(f"{API}/users")
        assert r.status_code == 401

    def test_admin_list_users(self, admin_session):
        r = admin_session.get(f"{API}/users")
        assert r.status_code == 200
        assert any(u["email"] == ADMIN_EMAIL for u in r.json())

    def test_admin_create_and_delete_user(self, admin_session):
        email = f"TEST_user_{uuid.uuid4().hex[:6]}@fatinpenhores.tl"
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": "abc123", "name": "Temp", "role": "staff"
        })
        assert r.status_code == 200
        uid = r.json()["id"]
        # delete
        r2 = admin_session.delete(f"{API}/users/{uid}")
        assert r2.status_code == 200

    def test_self_delete_blocked(self, admin_session):
        me = admin_session.get(f"{API}/auth/me").json()
        r = admin_session.delete(f"{API}/users/{me['id']}")
        assert r.status_code == 400

    def test_staff_cannot_list_users(self, staff_session):
        r = staff_session.get(f"{API}/users")
        assert r.status_code == 403


# -------- Clients --------
class TestClients:
    def test_create_list_update_delete(self, admin_session):
        payload = {
            "full_name": "TEST_Client Joao",
            "id_type": "BI",
            "id_number": "1234567",
            "phone": "+670 7777 0001",
            "address": "Rua Principal",
            "municipality": "Dili",
            "posto": "Vera Cruz",
            "suco": "Caicoli",
            "aldeia": "Aldeia 1",
            "notes": "",
        }
        r = admin_session.post(f"{API}/clients", json=payload)
        assert r.status_code == 200, r.text
        c = r.json()
        cid = c["id"]
        assert c["municipality"] == "Dili"
        # GET to confirm persistence
        g = admin_session.get(f"{API}/clients/{cid}")
        assert g.status_code == 200
        assert g.json()["full_name"] == "TEST_Client Joao"
        # Update
        payload["phone"] = "+670 1111 2222"
        u = admin_session.put(f"{API}/clients/{cid}", json=payload)
        assert u.status_code == 200
        assert u.json()["phone"] == "+670 1111 2222"
        # List contains
        l = admin_session.get(f"{API}/clients")
        assert any(x["id"] == cid for x in l.json())
        # Delete
        d = admin_session.delete(f"{API}/clients/{cid}")
        assert d.status_code == 200
        g2 = admin_session.get(f"{API}/clients/{cid}")
        assert g2.status_code == 404

    def test_staff_cannot_delete_client(self, admin_session, staff_session):
        r = admin_session.post(f"{API}/clients", json={
            "full_name": "TEST_DelMe", "id_type": "BI", "id_number": "0001",
            "phone": "+670 9000 0001"
        })
        cid = r.json()["id"]
        r2 = staff_session.delete(f"{API}/clients/{cid}")
        assert r2.status_code == 403
        admin_session.delete(f"{API}/clients/{cid}")


# -------- Items --------
class TestItems:
    def test_car_crud(self, admin_session):
        r = admin_session.post(f"{API}/items/car", json={
            "brand": "Toyota", "model": "Hilux", "plate": "DL-1234",
            "chassis": "CHX001", "fuel_percent": 75, "color": "white", "year": 2018
        })
        assert r.status_code == 200, r.text
        iid = r.json()["id"]
        assert r.json()["kind"] == "car"
        g = admin_session.get(f"{API}/items/car")
        assert any(x["id"] == iid for x in g.json())
        admin_session.delete(f"{API}/items/car/{iid}")

    def test_motorcycle_create(self, admin_session):
        r = admin_session.post(f"{API}/items/motorcycle", json={
            "brand": "Honda", "model": "CB150", "plate": "DM-7777", "fuel_percent": 50
        })
        assert r.status_code == 200
        admin_session.delete(f"{API}/items/motorcycle/{r.json()['id']}")

    def test_electronic_create(self, admin_session):
        r = admin_session.post(f"{API}/items/electronic", json={
            "category": "phone", "brand": "Samsung", "model": "S22", "serial": "SN001", "condition": "good"
        })
        assert r.status_code == 200
        admin_session.delete(f"{API}/items/electronic/{r.json()['id']}")

    def test_invalid_kind(self, admin_session):
        r = admin_session.get(f"{API}/items/bicycle")
        assert r.status_code == 400


# -------- Full flow: contract + payment + PDF + auction --------
class TestContractFlow:
    @pytest.fixture(scope="class")
    def seed(self, admin_session):
        c = admin_session.post(f"{API}/clients", json={
            "full_name": "TEST_Flow Client", "id_type": "Passport",
            "id_number": "P-9999", "phone": "+670 8800 0001",
            "municipality": "Baucau"
        }).json()
        item = admin_session.post(f"{API}/items/electronic", json={
            "category": "laptop", "brand": "Dell", "model": "XPS13", "serial": "SN-FLOW-1"
        }).json()
        yield {"client": c, "item": item}
        # cleanup
        admin_session.delete(f"{API}/clients/{c['id']}")
        admin_session.delete(f"{API}/items/electronic/{item['id']}")

    def test_create_contract_generates_number(self, admin_session, seed):
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": seed["client"]["id"],
            "item_id": seed["item"]["id"],
            "item_type": "electronic",
            "loan_amount": 100.0,
            "interest_rate": 10,
            "contract_date": "2025-01-01",
            "due_date": "2099-12-31",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["contract_number"].startswith("CTR-")
        assert body["status"] == "active"
        assert body["remaining_balance"] == 110.0
        # item marked pawned
        it = admin_session.get(f"{API}/items/electronic/{seed['item']['id']}").json()
        assert it["status"] == "pawned"
        seed["contract"] = body

    def test_contract_pdf(self, admin_session, seed):
        cid = seed["contract"]["id"]
        r = admin_session.get(f"{API}/contracts/{cid}/pdf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert len(r.content) > 500
        assert r.content[:4] == b"%PDF"

    def test_partial_payment_then_full(self, admin_session, seed):
        cid = seed["contract"]["id"]
        # partial 50
        r1 = admin_session.post(f"{API}/payments", json={
            "contract_id": cid, "amount": 50.0, "type": "partial", "date": "2025-01-15"
        })
        assert r1.status_code == 200
        assert r1.json()["contract"]["status"] == "active"
        assert r1.json()["contract"]["remaining_balance"] == 60.0
        # full remaining
        r2 = admin_session.post(f"{API}/payments", json={
            "contract_id": cid, "amount": 60.0, "type": "full", "date": "2025-01-20"
        })
        assert r2.status_code == 200
        assert r2.json()["contract"]["status"] == "redeemed"
        # item should be redeemed
        it = admin_session.get(f"{API}/items/electronic/{seed['item']['id']}").json()
        assert it["status"] == "redeemed"
        # receipt PDF
        pid = r2.json()["payment"]["id"]
        rp = admin_session.get(f"{API}/payments/{pid}/pdf")
        assert rp.status_code == 200
        assert rp.headers["content-type"] == "application/pdf"
        assert rp.content[:4] == b"%PDF"


class TestAuctionFlow:
    def test_overdue_to_auction_sold(self, admin_session):
        # seed
        c = admin_session.post(f"{API}/clients", json={
            "full_name": "TEST_Auction Client", "id_type": "BI",
            "id_number": "A-1", "phone": "+670 9 9", "municipality": "Dili"
        }).json()
        item = admin_session.post(f"{API}/items/car", json={
            "brand": "Ford", "model": "Ranger", "plate": "A-001"
        }).json()
        contract = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": item["id"], "item_type": "car",
            "loan_amount": 500.0, "interest_rate": 15,
            "contract_date": "2024-01-01", "due_date": "2024-01-31"
        }).json()
        # Trigger recompute by GET
        cc = admin_session.get(f"{API}/contracts/{contract['id']}").json()
        assert cc["status"] == "overdue"
        # Move to auction
        mv = admin_session.post(f"{API}/auctions/move", json={
            "contract_id": contract["id"], "starting_price": 600.0
        })
        assert mv.status_code == 200, mv.text
        aid = mv.json()["id"]
        # Public list
        pub = requests.get(f"{API}/auctions/public")
        assert pub.status_code == 200
        assert any(a["id"] == aid for a in pub.json())
        # Mark sold
        sold = admin_session.post(f"{API}/auctions/{aid}/sold", json={
            "sold_price": 650.0, "buyer_name": "Buyer A"
        })
        assert sold.status_code == 200
        assert sold.json()["status"] == "sold"
        # cleanup
        admin_session.delete(f"{API}/auctions/{aid}")
        admin_session.delete(f"{API}/contracts/{contract['id']}")
        admin_session.delete(f"{API}/items/car/{item['id']}")
        admin_session.delete(f"{API}/clients/{c['id']}")


# -------- Reports & Dashboard --------
class TestReports:
    @pytest.mark.parametrize("rtype", ["loans", "payments", "profit", "overdue", "clients", "contracts"])
    def test_report_returns_list(self, admin_session, rtype):
        r = admin_session.get(f"{API}/reports/{rtype}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_report_invalid(self, admin_session):
        r = admin_session.get(f"{API}/reports/foo")
        assert r.status_code == 400

    def test_dashboard_summary(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/summary")
        assert r.status_code == 200
        body = r.json()
        for k in ["total_clients", "active_contracts", "overdue_contracts",
                  "total_loan_amount", "total_payments", "profit"]:
            assert k in body


# -------- Public endpoints --------
class TestPublic:
    def test_public_auction_items(self):
        r = requests.get(f"{API}/public/auction-items")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_public_warehouse(self):
        r = requests.get(f"{API}/public/warehouse")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_public_contact(self):
        r = requests.post(f"{API}/public/contact", json={
            "name": "TEST_ContactUser",
            "email": "test_contact@example.com",
            "phone": "+670 1",
            "message": "Hello"
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True
