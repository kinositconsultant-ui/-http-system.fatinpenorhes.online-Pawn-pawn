"""Iter16 backend tests — Loan Disbursement auto-payment + contract PDF Article 4 bullets."""
import io
import os
from datetime import date, timedelta

import pytest
import requests
from pypdf import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pawnly-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def seed(admin_session):
    c = admin_session.post(f"{API}/clients", json={
        "full_name": "TEST_Iter16 Client",
        "id_type": "Passport",
        "id_number": f"P-ITER16-{date.today().isoformat()}",
        "phone": "+670 8800 1616",
        "municipality": "Dili",
    })
    assert c.status_code == 200, c.text
    client = c.json()
    it = admin_session.post(f"{API}/items/electronic", json={
        "category": "phone", "brand": "Samsung", "model": "S24", "serial": "SN-ITER16-1", "condition": "good"
    })
    assert it.status_code == 200, it.text
    item = it.json()
    yield {"client": client, "item": item}
    admin_session.delete(f"{API}/items/electronic/{item['id']}")
    admin_session.delete(f"{API}/clients/{client['id']}")


# ---- Feature 1: Auto-record Loan Disbursement Payment ----
class TestDisbursementAuto:
    @pytest.fixture(scope="class")
    def contract(self, admin_session, seed):
        today = date.today()
        due = today + timedelta(days=30)
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": seed["client"]["id"],
            "item_id": seed["item"]["id"],
            "item_type": "electronic",
            "loan_amount": 1000.0,
            "interest_rate": 15,
            "contract_date": today.isoformat(),
            "due_date": due.isoformat(),
        })
        assert r.status_code == 200, r.text
        c = r.json()
        yield c
        admin_session.delete(f"{API}/contracts/{c['id']}")

    def test_contract_created_status_and_balances(self, contract):
        # status active, paid_amount 0 (disbursement NOT counted)
        assert contract["status"] == "active"
        assert contract["paid_amount"] == 0
        assert contract["loan_amount"] == 1000.0
        # remaining = loan + interest
        expected_interest = 1000.0 * 15 / 100
        assert contract["remaining_balance"] == 1000.0 + expected_interest
        assert contract["principal_remaining"] == 1000.0
        assert contract["interest_remaining"] == expected_interest

    def test_iter10_regression_fields_present(self, contract):
        for k in ("days_overdue", "penalty", "penalty_paid"):
            assert k in contract, f"Missing iter10 field: {k}"

    def test_disbursement_payment_auto_created(self, admin_session, contract):
        r = admin_session.get(f"{API}/payments", params={"contract_id": contract["id"]})
        assert r.status_code == 200, r.text
        rows = r.json()
        disbs = [p for p in rows if p.get("type") == "disbursement"]
        assert len(disbs) == 1, f"Expected exactly one disbursement, got {len(disbs)}: {rows}"
        d = disbs[0]
        assert d["amount"] == contract["loan_amount"] == 1000.0
        assert d["date"] == contract["contract_date"]
        assert d["receipt_number"].startswith("RCP-"), d.get("receipt_number")
        assert d["contract_id"] == contract["id"]

    def test_disbursement_pdf_content(self, admin_session, contract):
        r = admin_session.get(f"{API}/payments", params={"contract_id": contract["id"]})
        disb = [p for p in r.json() if p.get("type") == "disbursement"][0]
        pdf_r = admin_session.get(f"{API}/payments/{disb['id']}/pdf")
        assert pdf_r.status_code == 200, pdf_r.text
        assert pdf_r.headers["content-type"] == "application/pdf"
        assert pdf_r.content[:4] == b"%PDF"
        reader = PdfReader(io.BytesIO(pdf_r.content))
        text = "".join((p.extract_text() or "") for p in reader.pages)
        # Title changed for disbursement
        assert ("Loan Disbursement Receipt" in text) or ("Resibu Entrega Empréstimu" in text) or ("Emprestimu" in text and "Entrega" in text), \
            f"Disbursement title missing. First 400 chars: {text[:400]}"
        assert "Amount Received" in text, f"'Amount Received' missing from disbursement PDF. Text: {text[:500]}"
        # Should NOT have repayment-only fields
        assert "Principal Remaining" not in text, "Repayment field 'Principal Remaining' should NOT appear in disbursement PDF"


# ---- Feature 2: Contract PDF Article 4 new bullets ----
class TestContractPdfArticle4:
    def test_contract_pdf_has_new_article4_lines(self, admin_session, seed):
        # create a temp contract just for PDF
        today = date.today()
        due = today + timedelta(days=30)
        item2 = admin_session.post(f"{API}/items/electronic", json={
            "category": "tv", "brand": "LG", "model": "OLED", "serial": "SN-ITER16-PDF", "condition": "good"
        }).json()
        try:
            r = admin_session.post(f"{API}/contracts", json={
                "client_id": seed["client"]["id"],
                "item_id": item2["id"],
                "item_type": "electronic",
                "loan_amount": 300.0,
                "interest_rate": 15,
                "contract_date": today.isoformat(),
                "due_date": due.isoformat(),
            })
            assert r.status_code == 200, r.text
            c = r.json()
            pdf_r = admin_session.get(f"{API}/contracts/{c['id']}/pdf")
            assert pdf_r.status_code == 200
            assert pdf_r.content[:4] == b"%PDF"
            reader = PdfReader(io.BytesIO(pdf_r.content))
            text = "".join((p.extract_text() or "") for p in reader.pages)
            # Existing text still present
            assert "fulan rua" in text, "Original Article 4 phrase missing"
            # New bullets present
            assert "Kontratu liu loron 1" in text, "New bullet 'Kontratu liu loron 1' missing"
            assert "Tolerasia" in text and "10 dias" in text, "New bullet 'Tolerasia 10 dias' missing"
            admin_session.delete(f"{API}/contracts/{c['id']}")
        finally:
            admin_session.delete(f"{API}/items/electronic/{item2['id']}")


# ---- Feature 3: Finance summary excludes disbursements from client_payments ----
class TestFinanceSummary:
    def test_finance_client_payments_excludes_disbursement(self, admin_session, seed):
        # baseline
        b = admin_session.get(f"{API}/finance/summary").json()
        base_client_payments = float(b.get("client_payments", 0))
        base_loans = float(b.get("loans_disbursed", 0))
        base_cash = float(b.get("cash_on_hand", 0))

        # create fresh item + contract with loan 1000
        item = admin_session.post(f"{API}/items/electronic", json={
            "category": "phone", "brand": "Nokia", "model": "X10", "serial": "SN-FIN-16", "condition": "good"
        }).json()
        today = date.today()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": seed["client"]["id"],
            "item_id": item["id"],
            "item_type": "electronic",
            "loan_amount": 1000.0,
            "interest_rate": 15,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=30)).isoformat(),
        })
        assert r.status_code == 200, r.text
        c = r.json()
        try:
            after = admin_session.get(f"{API}/finance/summary").json()
            assert float(after["client_payments"]) == pytest.approx(base_client_payments, abs=0.01), \
                f"client_payments changed! before={base_client_payments} after={after['client_payments']}"
            assert float(after["loans_disbursed"]) == pytest.approx(base_loans + 1000.0, abs=0.01)
            assert float(after["cash_on_hand"]) == pytest.approx(base_cash - 1000.0, abs=0.01)
        finally:
            admin_session.delete(f"{API}/contracts/{c['id']}")
            admin_session.delete(f"{API}/items/electronic/{item['id']}")


# ---- Regression: partial repayment still works, disbursement not counted ----
class TestRepaymentRegression:
    def test_partial_payment_updates_paid_amount(self, admin_session, seed):
        item = admin_session.post(f"{API}/items/electronic", json={
            "category": "phone", "brand": "Xiaomi", "model": "13", "serial": "SN-REG-16", "condition": "good"
        }).json()
        today = date.today()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": seed["client"]["id"],
            "item_id": item["id"],
            "item_type": "electronic",
            "loan_amount": 200.0,
            "interest_rate": 15,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=30)).isoformat(),
        })
        assert r.status_code == 200, r.text
        c = r.json()
        try:
            assert c["paid_amount"] == 0
            pay = admin_session.post(f"{API}/payments", json={
                "contract_id": c["id"],
                "amount": 50.0,
                "type": "partial",
                "date": today.isoformat(),
            })
            assert pay.status_code == 200, pay.text
            body = pay.json()
            updated = body.get("contract") or body
            assert float(updated["paid_amount"]) == pytest.approx(50.0, abs=0.01)
            # remaining should be (200 + 200*0.15) - 50 = 180
            assert float(updated["remaining_balance"]) == pytest.approx(180.0, abs=0.01)
        finally:
            admin_session.delete(f"{API}/contracts/{c['id']}")
            admin_session.delete(f"{API}/items/electronic/{item['id']}")
