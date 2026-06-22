"""Iteration 6 branding tests — verify PDFs include the FP logo (size > 30KB) and Excel still works."""
import os
import requests
import pytest
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pawnly-pro.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def contract_id(admin_session):
    """Create a client, car item, contract and partial payment to test PDFs."""
    s = admin_session
    ts = int(__import__("time").time())
    c = s.post(f"{BASE_URL}/api/clients", json={
        "full_name": f"TEST_iter6_{ts}", "phone": "+670 7700 0000",
        "address": "Caicoli", "id_type": "Passport", "id_number": f"P{ts}",
    })
    assert c.status_code in (200, 201), c.text
    client_id = c.json()["id"]

    it = s.post(f"{BASE_URL}/api/items/car", json={
        "brand": "TEST_Toyota", "model": "Hilux",
        "manufacture_year": 2020, "plate": f"T-{ts%10000}",
        "appraised_value": 5000.0, "market_value": 6000.0, "location": "Warehouse A",
    })
    assert it.status_code in (200, 201), it.text
    item_id = it.json()["id"]

    today = date.today()
    due = today + timedelta(days=30)
    co = s.post(f"{BASE_URL}/api/contracts", json={
        "client_id": client_id, "item_id": item_id, "item_type": "car",
        "loan_amount": 1000.0, "interest_rate": 10,
        "contract_date": today.isoformat(), "due_date": due.isoformat(),
    })
    assert co.status_code in (200, 201), co.text
    return co.json()["id"]


@pytest.fixture(scope="module")
def payment_id(admin_session, contract_id):
    s = admin_session
    p = s.post(f"{BASE_URL}/api/payments", json={
        "contract_id": contract_id, "amount": 100.0,
        "date": date.today().isoformat(), "type": "interest_only",
    })
    assert p.status_code in (200, 201), p.text
    j = p.json()
    return j.get("payment", j).get("id") or j.get("id")


def _assert_pdf(resp, min_kb: int = 30):
    assert resp.status_code == 200, f"status={resp.status_code} body={resp.text[:300]}"
    ct = resp.headers.get("content-type", "")
    assert "application/pdf" in ct, f"content-type={ct}"
    body = resp.content
    assert body[:4] == b"%PDF", f"head={body[:8]!r}"
    size_kb = len(body) / 1024.0
    assert size_kb > min_kb, f"pdf size {size_kb:.1f}KB <= {min_kb}KB (expected logo embedded)"


class TestBrandedPDFs:
    """Branded PDFs should embed the FP logo making them > 30KB."""

    def test_contract_pdf_with_logo(self, admin_session, contract_id):
        r = admin_session.get(f"{BASE_URL}/api/contracts/{contract_id}/pdf")
        _assert_pdf(r, min_kb=30)

    def test_receipt_pdf_with_logo(self, admin_session, payment_id):
        r = admin_session.get(f"{BASE_URL}/api/payments/{payment_id}/pdf")
        _assert_pdf(r, min_kb=30)

    def test_report_financial_pdf(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/reports/v2/financial/export?format=pdf")
        _assert_pdf(r, min_kb=30)

    def test_report_active_contracts_pdf(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/reports/v2/active-contracts/export?format=pdf")
        _assert_pdf(r, min_kb=30)


class TestExcelExport:
    def test_financial_xlsx(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/reports/v2/financial/export?format=xlsx")
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "openxmlformats" in ct, f"content-type={ct}"
        assert len(r.content) > 4 * 1024, f"xlsx size {len(r.content)} bytes <= 4KB"
        assert r.content[:2] == b"PK", f"head={r.content[:4]!r}"


class TestPublicSmoke:
    def test_public_warehouse(self):
        r = requests.get(f"{BASE_URL}/api/public/warehouse")
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))
