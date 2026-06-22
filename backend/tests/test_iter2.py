"""Iteration 2 tests: settings, audit-log, whatsapp (mocked),
upload/download, dashboard trends, cashier role, payment date validation,
contract default rate, richer PDF."""
import os
import io
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://pawnly-pro.preview.emergentagent.com"
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def staff(admin):
    email = f"TEST_staff_{uuid.uuid4().hex[:6]}@fatinpenhores.tl"
    pw = "staff123!"
    r = admin.post(f"{API}/users", json={"email": email, "password": pw, "name": "Test Staff", "role": "staff"})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    s._uid = r.json()["id"]
    s._email = email
    s._password = pw
    return s


@pytest.fixture(scope="module")
def cashier(admin):
    email = f"TEST_cashier_{uuid.uuid4().hex[:6]}@fatinpenhores.tl"
    pw = "cash123!"
    r = admin.post(f"{API}/users", json={"email": email, "password": pw, "name": "Test Cashier", "role": "cashier"})
    assert r.status_code == 200, r.text
    s = requests.Session()
    lr = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert lr.status_code == 200, lr.text
    s._uid = r.json()["id"]
    return s


# ---------- Settings ----------
class TestSettings:
    def test_get_defaults(self, admin):
        r = admin.get(f"{API}/settings")
        assert r.status_code == 200
        s = r.json()
        # default rates
        assert s.get("interest_rate_car") == 10
        assert s.get("interest_rate_motorcycle") == 15
        assert s.get("interest_rate_electronic") == 15
        # bilingual T&C
        assert s.get("terms_and_conditions_en"), "EN T&C missing"
        assert s.get("terms_and_conditions_tet"), "TET T&C missing"

    def test_put_updates_and_audit(self, admin):
        r = admin.get(f"{API}/settings")
        cur = r.json()
        new_payload = {
            "interest_rate_car": 12,
            "interest_rate_motorcycle": cur.get("interest_rate_motorcycle", 15),
            "interest_rate_electronic": cur.get("interest_rate_electronic", 15),
            "terms_and_conditions_en": cur.get("terms_and_conditions_en", "EN") + " v2",
            "terms_and_conditions_tet": cur.get("terms_and_conditions_tet", "TET") + " v2",
            "whatsapp_template_en": cur.get("whatsapp_template_en", "due_date_reminder"),
            "whatsapp_template_tet": cur.get("whatsapp_template_tet", "due_date_reminder"),
            "whatsapp_token": "",
            "whatsapp_phone_id": "",
            "reminder_days_before": 3,
        }
        u = admin.put(f"{API}/settings", json=new_payload)
        assert u.status_code == 200, u.text
        assert u.json()["interest_rate_car"] == 12
        # restore for downstream tests
        new_payload["interest_rate_car"] = 10
        admin.put(f"{API}/settings", json=new_payload)
        # audit log entry should exist
        a = admin.get(f"{API}/audit-log", params={"resource": "settings"})
        assert a.status_code == 200
        assert any(x["action"] == "update" and x["resource"] == "settings" for x in a.json())

    def test_settings_put_non_admin(self, staff):
        r = staff.put(f"{API}/settings", json={
            "interest_rate_car": 10, "interest_rate_motorcycle": 15, "interest_rate_electronic": 15,
            "terms_and_conditions_en": "x", "terms_and_conditions_tet": "y",
            "whatsapp_template_en": "", "whatsapp_template_tet": "",
            "whatsapp_token": "", "whatsapp_phone_id": "", "reminder_days_before": 3,
        })
        assert r.status_code == 403


# ---------- Contract default rate ----------
class TestContractDefaultRate:
    @pytest.fixture
    def seed_client(self, admin):
        c = admin.post(f"{API}/clients", json={
            "full_name": "TEST_RateClient", "id_type": "BI", "id_number": "R1",
            "phone": "+670 9", "municipality": "Dili",
        }).json()
        yield c
        admin.delete(f"{API}/clients/{c['id']}")

    def test_rate_honored_when_provided(self, admin, seed_client):
        item = admin.post(f"{API}/items/car", json={"brand": "Toyota", "model": "Yaris", "plate": "C-1"}).json()
        ct = admin.post(f"{API}/contracts", json={
            "client_id": seed_client["id"], "item_id": item["id"], "item_type": "car",
            "loan_amount": 100.0, "interest_rate": 15,
            "contract_date": "2025-06-01", "due_date": "2025-12-31",
        })
        assert ct.status_code == 200, ct.text
        assert ct.json()["interest_rate"] == 15
        admin.delete(f"{API}/contracts/{ct.json()['id']}")
        admin.delete(f"{API}/items/car/{item['id']}")

    def test_rate_omitted_uses_settings_default(self, admin, seed_client):
        """Spec: when interest_rate omitted -> default by item_type from settings."""
        item = admin.post(f"{API}/items/motorcycle", json={"brand": "Honda", "model": "CB", "plate": "M-1"}).json()
        ct = admin.post(f"{API}/contracts", json={
            "client_id": seed_client["id"], "item_id": item["id"], "item_type": "motorcycle",
            "loan_amount": 100.0,
            "contract_date": "2025-06-01", "due_date": "2025-12-31",
        })
        # NOTE: ContractIn declares interest_rate as required Literal[10,15] -> Pydantic 422.
        # We assert the spec behavior, allowing for current bug.
        if ct.status_code == 422:
            pytest.fail("BUG: omitting interest_rate yields 422 — ContractIn marks it required; default-from-settings path is unreachable.")
        assert ct.status_code == 200, ct.text
        assert ct.json()["interest_rate"] == 15  # motorcycle default
        admin.delete(f"{API}/contracts/{ct.json()['id']}")
        admin.delete(f"{API}/items/motorcycle/{item['id']}")


# ---------- Contract PDF richer ----------
class TestContractPdfRicher:
    def test_pdf_more_than_3kb(self, admin):
        c = admin.post(f"{API}/clients", json={
            "full_name": "TEST_PdfClient", "id_type": "Passport", "id_number": "P-1",
            "phone": "+670 1", "municipality": "Dili",
        }).json()
        item = admin.post(f"{API}/items/electronic", json={
            "category": "phone", "brand": "Samsung", "model": "A50", "serial": "SN-PDF-1"
        }).json()
        ct = admin.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": item["id"], "item_type": "electronic",
            "loan_amount": 200.0, "interest_rate": 15,
            "contract_date": "2025-06-01", "due_date": "2025-12-31",
        }).json()
        r = admin.get(f"{API}/contracts/{ct['id']}/pdf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 3000, f"PDF too small: {len(r.content)} bytes (expected >3KB)"
        admin.delete(f"{API}/contracts/{ct['id']}")
        admin.delete(f"{API}/items/electronic/{item['id']}")
        admin.delete(f"{API}/clients/{c['id']}")


# ---------- Payment date validation ----------
class TestPaymentDateValidation:
    def test_payment_before_contract_date_rejected(self, admin):
        c = admin.post(f"{API}/clients", json={
            "full_name": "TEST_PayDate", "id_type": "BI", "id_number": "PD-1",
            "phone": "+670 2", "municipality": "Dili",
        }).json()
        item = admin.post(f"{API}/items/electronic", json={
            "category": "phone", "brand": "X", "model": "Y", "serial": "PD-1"
        }).json()
        ct = admin.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": item["id"], "item_type": "electronic",
            "loan_amount": 100.0, "interest_rate": 10,
            "contract_date": "2025-06-01", "due_date": "2025-12-31",
        }).json()
        bad = admin.post(f"{API}/payments", json={
            "contract_id": ct["id"], "amount": 10.0, "type": "partial", "date": "2025-05-01"
        })
        assert bad.status_code == 400, bad.text
        admin.delete(f"{API}/contracts/{ct['id']}")
        admin.delete(f"{API}/items/electronic/{item['id']}")
        admin.delete(f"{API}/clients/{c['id']}")


# ---------- Upload / Download ----------
class TestUploadDownload:
    def test_upload_and_download(self, admin):
        # 1x1 PNG (89 bytes)
        png = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
            "890000000D49444154789C6360000200000005000148AFC4970000000049454E44AE426082"
        )
        files = {"file": ("test.png", io.BytesIO(png), "image/png")}
        r = admin.post(f"{API}/upload", files=files)
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec.get("storage_path"), rec
        assert rec.get("url", "").startswith("/api/files/")
        path = rec["storage_path"]
        # cookie auth -> download
        g = admin.get(f"{API}/files/{path}")
        assert g.status_code == 200, g.text
        assert g.content == png
        # No-auth -> 401
        g2 = requests.get(f"{API}/files/{path}")
        assert g2.status_code == 401


# ---------- Dashboard trends ----------
class TestDashboardTrends:
    def test_trends_shape(self, admin):
        r = admin.get(f"{API}/dashboard/trends")
        assert r.status_code == 200
        body = r.json()
        assert "months" in body and isinstance(body["months"], list)
        assert len(body["months"]) == 6
        assert "overdue_by_type" in body
        types = {x["type"] for x in body["overdue_by_type"]}
        assert {"car", "motorcycle", "electronic"}.issubset(types)


# ---------- WhatsApp ----------
class TestWhatsApp:
    @pytest.fixture(scope="class")
    def contract(self, admin):
        c = admin.post(f"{API}/clients", json={
            "full_name": "TEST_WA", "id_type": "BI", "id_number": "W-1",
            "phone": "+670 7000 0001", "municipality": "Dili",
        }).json()
        item = admin.post(f"{API}/items/car", json={"brand": "T", "model": "M", "plate": "WA-1"}).json()
        ct = admin.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": item["id"], "item_type": "car",
            "loan_amount": 100.0, "interest_rate": 10,
            "contract_date": "2025-01-01", "due_date": "2025-12-31",
        }).json()
        yield ct
        admin.delete(f"{API}/contracts/{ct['id']}")
        admin.delete(f"{API}/items/car/{item['id']}")
        admin.delete(f"{API}/clients/{c['id']}")

    def test_send_returns_mocked(self, admin, contract):
        r = admin.post(f"{API}/whatsapp/send", json={"contract_id": contract["id"], "language": "en"})
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "mocked"

    def test_logs_contains_send(self, admin, contract):
        r = admin.get(f"{API}/whatsapp/logs")
        assert r.status_code == 200
        assert any(x["contract_id"] == contract["id"] for x in r.json())

    def test_reminders_run(self, admin):
        r = admin.post(f"{API}/whatsapp/reminders/run", params={"language": "en"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "count" in body and "sent" in body
        assert isinstance(body["sent"], list)


# ---------- Audit log RBAC ----------
class TestAuditLog:
    def test_admin_can_list(self, admin):
        r = admin.get(f"{API}/audit-log")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_staff_forbidden(self, staff):
        r = staff.get(f"{API}/audit-log")
        assert r.status_code == 403

    def test_filter_by_resource(self, admin):
        r = admin.get(f"{API}/audit-log", params={"resource": "contract"})
        assert r.status_code == 200
        for x in r.json():
            assert x["resource"] == "contract"


# ---------- Cashier role ----------
class TestCashierRBAC:
    @pytest.fixture(scope="class")
    def seed_for_payment(self, admin):
        c = admin.post(f"{API}/clients", json={
            "full_name": "TEST_CashierFlow", "id_type": "BI", "id_number": "CF-1",
            "phone": "+670 6000 0001", "municipality": "Dili",
        }).json()
        item = admin.post(f"{API}/items/electronic", json={
            "category": "phone", "brand": "X", "model": "Y", "serial": "CF-1"
        }).json()
        ct = admin.post(f"{API}/contracts", json={
            "client_id": c["id"], "item_id": item["id"], "item_type": "electronic",
            "loan_amount": 100.0, "interest_rate": 10,
            "contract_date": "2025-01-01", "due_date": "2099-12-31",
        }).json()
        yield {"client": c, "item": item, "contract": ct}
        admin.delete(f"{API}/contracts/{ct['id']}")
        admin.delete(f"{API}/items/electronic/{item['id']}")
        admin.delete(f"{API}/clients/{c['id']}")

    def test_cashier_cannot_create_client(self, cashier):
        r = cashier.post(f"{API}/clients", json={
            "full_name": "TEST_CashierClient", "id_type": "BI", "id_number": "X",
            "phone": "+670 1", "municipality": "Dili",
        })
        assert r.status_code == 403, f"Expected 403 but got {r.status_code}: {r.text}"

    def test_cashier_cannot_create_car_item(self, cashier):
        r = cashier.post(f"{API}/items/car", json={"brand": "T", "model": "M", "plate": "CASH-1"})
        assert r.status_code == 403, f"Expected 403 but got {r.status_code}: {r.text}"

    def test_cashier_cannot_create_contract(self, cashier, seed_for_payment):
        r = cashier.post(f"{API}/contracts", json={
            "client_id": seed_for_payment["client"]["id"],
            "item_id": seed_for_payment["item"]["id"],
            "item_type": "electronic",
            "loan_amount": 50.0, "interest_rate": 10,
            "contract_date": "2025-01-01", "due_date": "2099-12-31",
        })
        assert r.status_code == 403

    def test_cashier_can_create_payment(self, cashier, seed_for_payment):
        r = cashier.post(f"{API}/payments", json={
            "contract_id": seed_for_payment["contract"]["id"],
            "amount": 5.0, "type": "partial", "date": "2025-02-01"
        })
        assert r.status_code == 200, r.text


# ---------- Staff RBAC regression ----------
class TestStaffRBAC:
    def test_staff_cannot_list_users(self, staff):
        r = staff.get(f"{API}/users")
        assert r.status_code == 403

    def test_staff_cannot_view_audit_log(self, staff):
        r = staff.get(f"{API}/audit-log")
        assert r.status_code == 403

    def test_staff_can_create_client(self, staff):
        r = staff.post(f"{API}/clients", json={
            "full_name": "TEST_StaffClient", "id_type": "BI", "id_number": "S-1",
            "phone": "+670 1", "municipality": "Dili",
        })
        assert r.status_code == 200, r.text
        # cleanup as admin via session not available; ignore
