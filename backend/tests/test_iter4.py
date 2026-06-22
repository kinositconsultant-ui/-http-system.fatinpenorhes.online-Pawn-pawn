"""Iteration 4 backend tests: photo_url, Drivers License, market_value,
manufacture_year, 62-day contract limit, principal/interest payment split,
penalty, reactivate, /clients/{id}/payments, PDF format."""
import os
import time
import requests
from datetime import date, timedelta

import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def cashier_session(admin_session):
    email = f"TEST_cashier_iter4_{int(time.time())}@x.tl"
    pw = "cashpass123"
    r = admin_session.post(f"{API}/users", json={"email": email, "password": pw, "name": "TEST Cashier", "role": "cashier"})
    assert r.status_code in (200, 201, 409), r.text
    s = requests.Session()
    r2 = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r2.status_code == 200, r2.text
    return s


def _create_client(admin, **over):
    payload = {
        "full_name": f"TEST Iter4 {int(time.time()*1000)}",
        "id_type": "BI",
        "id_number": f"TEST{int(time.time()*1000)}",
        "phone": "+67012345678",
    }
    payload.update(over)
    r = admin.post(f"{API}/clients", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _create_car(admin, **over):
    payload = {"brand": "TEST Toyota", "model": "Corolla", "plate": f"T-{int(time.time()*1000)}"}
    payload.update(over)
    r = admin.post(f"{API}/items/car", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- clients: Drivers License + photo_url ----------
class TestClientsIter4:
    def test_drivers_license_accepted(self, admin_session):
        c = _create_client(admin_session, id_type="Drivers License", photo_url="fatin-penhores/uploads/x/photo.jpg")
        assert c["id_type"] == "Drivers License"
        assert c["photo_url"].endswith("photo.jpg")
        r = admin_session.get(f"{API}/clients/{c['id']}")
        assert r.status_code == 200
        assert r.json()["id_type"] == "Drivers License"

    def test_invalid_id_type_422(self, admin_session):
        r = admin_session.post(f"{API}/clients", json={
            "full_name": "TEST bad", "id_type": "FakeID",
            "id_number": "X", "phone": "+670"
        })
        assert r.status_code == 422

    def test_client_contracts_and_payments_endpoints(self, admin_session):
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        today = date.today()
        ctr = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 3000, "interest_rate": 10,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=30)).isoformat(),
        })
        assert ctr.status_code == 200, ctr.text
        cnum = ctr.json()["contract_number"]
        # payment
        pay = admin_session.post(f"{API}/payments", json={
            "contract_id": ctr.json()["id"], "amount": 100, "type": "interest_only",
            "date": today.isoformat(),
        })
        assert pay.status_code == 200, pay.text

        rc = admin_session.get(f"{API}/clients/{c['id']}/contracts")
        assert rc.status_code == 200
        assert any(x["contract_number"] == cnum for x in rc.json())

        rp = admin_session.get(f"{API}/clients/{c['id']}/payments")
        assert rp.status_code == 200
        rows = rp.json()
        assert len(rows) >= 1
        assert rows[0].get("contract_number") == cnum
        assert rows[0].get("item_type") == "car"


# ---------- items: manufacture_year + market_value ----------
class TestItemsIter4:
    def test_car_manufacture_year_and_market_value(self, admin_session):
        car = _create_car(admin_session, manufacture_year=2018, market_value=12500.50)
        assert car["manufacture_year"] == 2018
        assert car["market_value"] == 12500.50
        assert "year" not in car  # legacy field removed

    def test_car_ignores_legacy_year(self, admin_session):
        car = _create_car(admin_session, year=2020)  # should be ignored, default None
        assert car.get("manufacture_year") is None

    def test_motorcycle_supports_new_fields(self, admin_session):
        r = admin_session.post(f"{API}/items/motorcycle", json={
            "brand": "TEST Honda", "model": "PCX",
            "manufacture_year": 2021, "market_value": 1500.0,
        })
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["manufacture_year"] == 2021 and m["market_value"] == 1500.0

    def test_electronic_supports_new_fields(self, admin_session):
        r = admin_session.post(f"{API}/items/electronic", json={
            "category": "phone", "brand": "TEST Samsung", "model": "S22",
            "manufacture_year": 2023, "market_value": 800.0,
        })
        assert r.status_code == 200, r.text


# ---------- contracts: 62-day cap ----------
class TestContractValidation:
    def test_due_before_contract_date_422(self, admin_session):
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        today = date.today()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 1000,
            "contract_date": today.isoformat(),
            "due_date": (today - timedelta(days=1)).isoformat(),
        })
        assert r.status_code == 422

    def test_over_62_days_422(self, admin_session):
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        today = date.today()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 1000,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=70)).isoformat(),
        })
        assert r.status_code == 422

    def test_62_days_exact_ok(self, admin_session):
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        today = date.today()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 1000,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=62)).isoformat(),
        })
        assert r.status_code == 200, r.text


# ---------- payment math ----------
class TestPaymentMath:
    def _setup(self, admin_session):
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        today = date.today()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 3000, "interest_rate": 10,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=30)).isoformat(),
        })
        assert r.status_code == 200, r.text
        return r.json(), today

    def test_partial_reduces_principal(self, admin_session):
        ctr, today = self._setup(admin_session)
        r = admin_session.post(f"{API}/payments", json={
            "contract_id": ctr["id"], "amount": 1000, "type": "partial",
            "date": today.isoformat(),
        })
        assert r.status_code == 200, r.text
        c = r.json()["contract"]
        assert c["principal_paid"] == 1000
        assert c["principal_remaining"] == 2000
        assert c["interest_remaining"] == 300
        assert c["interest_amount"] == 300
        # total_due = 2300 + penalty (0 because not overdue)
        assert c["total_due"] == 2300

    def test_interest_only_then_partial(self, admin_session):
        ctr, today = self._setup(admin_session)
        r = admin_session.post(f"{API}/payments", json={
            "contract_id": ctr["id"], "amount": 300, "type": "interest_only",
            "date": today.isoformat(),
        })
        assert r.status_code == 200, r.text
        c = r.json()["contract"]
        assert c["interest_paid"] == 300
        assert c["interest_remaining"] == 0
        assert c["principal_remaining"] == 3000


# ---------- penalty + reactivate ----------
class TestPenaltyAndReactivate:
    def _make_overdue(self, admin_session):
        """Create a contract with due_date yesterday so it's overdue."""
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        two_days_ago = (date.today() - timedelta(days=2)).isoformat()
        # contract_date <= due_date and within 62 days
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 2000, "interest_rate": 10,
            "contract_date": two_days_ago,
            "due_date": yesterday,
        })
        assert r.status_code == 200, r.text
        return r.json()

    def test_overdue_applies_penalty(self, admin_session):
        ctr = self._make_overdue(admin_session)
        r = admin_session.get(f"{API}/contracts/{ctr['id']}")
        assert r.status_code == 200
        c = r.json()
        assert c["status"] == "overdue"
        assert c["penalty"] == round(2000 * 0.10, 2)  # 200.0
        assert c["total_due"] == 2000 + 200 + 200  # principal + interest + penalty

    def test_reactivate_clears_penalty_and_flips_to_active(self, admin_session):
        ctr = self._make_overdue(admin_session)
        new_due = (date.today() + timedelta(days=20)).isoformat()
        r = admin_session.post(f"{API}/contracts/{ctr['id']}/reactivate", json={
            "new_due_date": new_due, "notes": "extended"
        })
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["status"] == "active"
        assert c["penalty"] == 0
        # verify persisted
        r2 = admin_session.get(f"{API}/contracts/{ctr['id']}")
        assert r2.json()["due_date"] == new_due

    def test_reactivate_past_date_422(self, admin_session):
        ctr = self._make_overdue(admin_session)
        r = admin_session.post(f"{API}/contracts/{ctr['id']}/reactivate", json={
            "new_due_date": (date.today() - timedelta(days=1)).isoformat(),
        })
        assert r.status_code == 422

    def test_reactivate_today_422(self, admin_session):
        ctr = self._make_overdue(admin_session)
        r = admin_session.post(f"{API}/contracts/{ctr['id']}/reactivate", json={
            "new_due_date": date.today().isoformat(),
        })
        assert r.status_code == 422

    def test_reactivate_over_62_days_422(self, admin_session):
        ctr = self._make_overdue(admin_session)
        r = admin_session.post(f"{API}/contracts/{ctr['id']}/reactivate", json={
            "new_due_date": (date.today() + timedelta(days=70)).isoformat(),
        })
        assert r.status_code == 422


# ---------- PDF ----------
class TestContractPDF:
    def test_pdf_returned(self, admin_session):
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        today = date.today()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 1500, "interest_rate": 10,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=30)).isoformat(),
        })
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        pdf = admin_session.get(f"{API}/contracts/{cid}/pdf")
        assert pdf.status_code == 200
        assert pdf.headers["content-type"].startswith("application/pdf")
        assert pdf.content[:4] == b"%PDF"
        assert len(pdf.content) > 4096


# ---------- RBAC ----------
class TestRBAC:
    def test_cashier_cannot_create_client(self, cashier_session):
        r = cashier_session.post(f"{API}/clients", json={
            "full_name": "TEST nope", "id_type": "BI", "id_number": "X", "phone": "+670"
        })
        assert r.status_code == 403

    def test_cashier_cannot_create_item(self, cashier_session):
        r = cashier_session.post(f"{API}/items/car", json={"brand": "X", "model": "Y", "plate": "Z"})
        assert r.status_code == 403

    def test_cashier_cannot_create_contract(self, admin_session, cashier_session):
        # admin sets up entities, cashier tries to create contract
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        today = date.today()
        r = cashier_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 1000,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=10)).isoformat(),
        })
        assert r.status_code == 403

    def test_cashier_cannot_reactivate(self, admin_session, cashier_session):
        c = _create_client(admin_session)
        car = _create_car(admin_session)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        two_days_ago = (date.today() - timedelta(days=2)).isoformat()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": car["id"], "item_type": "car",
            "loan_amount": 1000, "interest_rate": 10,
            "contract_date": two_days_ago, "due_date": yesterday,
        })
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        new_due = (date.today() + timedelta(days=20)).isoformat()
        r2 = cashier_session.post(f"{API}/contracts/{cid}/reactivate", json={"new_due_date": new_due})
        assert r2.status_code == 403
