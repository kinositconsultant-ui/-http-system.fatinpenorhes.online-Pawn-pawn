"""Iteration 7 — Finance/Treasury + WhatsApp branding tests.

Covers:
- funding_sources CRUD + repayments
- expenses CRUD + category list + role guard (cashier 403)
- /api/finance/summary numeric fields + math (capital, expenses, repayment effect)
- /api/reports/v2/treasury (json) and exports (xlsx/pdf)
- PDF header now uses "WhatsApp: +670 78372678"
"""
import os
import io
import re
import time
import requests
import pytest
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# -------- Fixtures --------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def cashier(admin):
    """Create or reuse a cashier user and return an authed session."""
    ts = int(time.time())
    email = f"TEST_cashier_{ts}@x.tl"
    password = "Cashier123!"
    # try creating
    r = admin.post(f"{BASE_URL}/api/users", json={
        "email": email, "password": password, "name": "TEST Cashier",
        "full_name": "TEST Cashier", "role": "cashier",
    })
    if r.status_code not in (200, 201):
        pytest.skip(f"could not create cashier: {r.status_code} {r.text[:200]}")
    s = requests.Session()
    lr = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if lr.status_code != 200:
        pytest.skip(f"cashier login failed: {lr.status_code} {lr.text[:200]}")
    return s


# -------- Expense categories --------
class TestExpenseCategories:
    def test_list_categories(self, admin):
        r = admin.get(f"{BASE_URL}/api/expense-categories")
        assert r.status_code == 200
        payload = r.json()
        # New response: {groups: [...], flat: [...]}
        assert "flat" in payload and "groups" in payload
        cats = set(payload["flat"])
        expected = {"Salary", "Maintenance", "Travel", "Meals", "Compensation", "Utilities", "Rent", "Other"}
        assert expected.issubset(cats), f"got={cats}"
        # 13 new categories added
        new_expected = {
            "EDTL token Office", "EDTL token Armazen", "Mina Trasporte",
            "Hadia Trasporte Lelaun No Elektróniku", "Internet Starlink & Telemor",
            "Pulsa telefone", "Fo Bónus", "Broker Trata Dokumentus", "Gastus Jerál",
            "Hola Materiál - Armazen 2", "Trasporte - Armazen 2",
            "Selu Badain - Armazen 2", "Tabela ATK FP - Armazen 2",
        }
        assert new_expected.issubset(cats), f"missing new categories: {new_expected - cats}"


# -------- Funding sources --------
class TestFundingSources:
    src_id = None

    def test_create_source(self, admin):
        ts = int(time.time())
        r = admin.post(f"{BASE_URL}/api/funding-sources", json={
            "name": f"TEST_Cap_{ts}", "source_type": "bank",
            "principal_amount": 50000, "interest_rate": 5.5,
            "interest_period": "monthly",
            "start_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=365)).isoformat(),
            "notes": "test",
        })
        assert r.status_code in (200, 201), r.text
        j = r.json()
        assert j["principal_amount"] == 50000
        assert j["total_repaid"] == 0
        assert j["outstanding"] == 50000
        TestFundingSources.src_id = j["id"]

    def test_list_includes_source(self, admin):
        r = admin.get(f"{BASE_URL}/api/funding-sources")
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert TestFundingSources.src_id in ids
        row = next(x for x in r.json() if x["id"] == TestFundingSources.src_id)
        assert "total_repaid" in row and "outstanding" in row

    def test_update_source(self, admin):
        r = admin.put(f"{BASE_URL}/api/funding-sources/{TestFundingSources.src_id}", json={
            "name": "TEST_Cap_updated", "source_type": "company",
            "principal_amount": 50000, "interest_rate": 6.0,
            "interest_period": "monthly",
            "start_date": date.today().isoformat(),
        })
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_Cap_updated"
        assert r.json()["source_type"] == "company"

    def test_repayment_decreases_outstanding(self, admin):
        # create
        r = admin.post(f"{BASE_URL}/api/funding-sources/{TestFundingSources.src_id}/repayments", json={
            "source_id": TestFundingSources.src_id, "amount": 5000,
            "date": date.today().isoformat(), "notes": "first repay",
        })
        assert r.status_code in (200, 201), r.text
        # list and verify outstanding = 45000
        lst = admin.get(f"{BASE_URL}/api/funding-sources").json()
        row = next(x for x in lst if x["id"] == TestFundingSources.src_id)
        assert row["total_repaid"] == 5000
        assert row["outstanding"] == 45000


# -------- Expenses --------
class TestExpenses:
    eid = None

    def test_create_expense_admin(self, admin):
        r = admin.post(f"{BASE_URL}/api/expenses", json={
            "category": "Utilities", "amount": 1200,
            "date": date.today().isoformat(),
            "paid_to": "TEST Utility Co", "description": "TEST_iter7 elec",
            "payment_method": "bank",
        })
        assert r.status_code in (200, 201), r.text
        j = r.json()
        assert j["amount"] == 1200
        assert j["category"] == "Utilities"
        TestExpenses.eid = j["id"]

    def test_cashier_forbidden_on_create(self, cashier):
        r = cashier.post(f"{BASE_URL}/api/expenses", json={
            "category": "Salary", "amount": 100, "date": date.today().isoformat(),
        })
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_list_filters(self, admin):
        today = date.today()
        r = admin.get(f"{BASE_URL}/api/expenses", params={
            "month": today.month, "year": today.year, "category": "Utilities",
        })
        assert r.status_code == 200
        rows = r.json()
        assert any(x["id"] == TestExpenses.eid for x in rows)
        assert all(x.get("category") == "Utilities" for x in rows)

    def test_update_expense_admin(self, admin):
        r = admin.put(f"{BASE_URL}/api/expenses/{TestExpenses.eid}", json={
            "category": "Utilities", "amount": 1300,
            "date": date.today().isoformat(),
            "paid_to": "TEST Utility Co", "description": "TEST_iter7 elec updated",
            "payment_method": "bank",
        })
        assert r.status_code == 200
        assert r.json()["amount"] == 1300

    def test_delete_expense_admin_at_end(self, admin):
        # delete a separate transient expense to keep TestExpenses.eid for summary
        r = admin.post(f"{BASE_URL}/api/expenses", json={
            "category": "Other", "amount": 1.0, "date": date.today().isoformat(),
            "paid_to": "TEST tmp",
        })
        assert r.status_code in (200, 201)
        tmp_id = r.json()["id"]
        d = admin.delete(f"{BASE_URL}/api/expenses/{tmp_id}")
        assert d.status_code in (200, 204)


# -------- Finance summary --------
class TestFinanceSummary:
    def test_summary_has_numeric_keys(self, admin):
        r = admin.get(f"{BASE_URL}/api/finance/summary")
        assert r.status_code == 200, r.text
        j = r.json()
        keys = ["cash_on_hand", "capital_received", "capital_repaid", "capital_outstanding",
                "loans_disbursed", "client_payments", "auction_sales", "expenses_total",
                "expenses_period", "interest_received", "total_penalty",
                "gross_profit", "net_profit", "expenses_by_category"]
        for k in keys:
            assert k in j, f"missing {k}"
        for k in keys[:-1]:
            assert isinstance(j[k], (int, float)), f"{k} not numeric: {type(j[k])}"
        assert isinstance(j["expenses_by_category"], list)

    def test_summary_reflects_capital_and_repayment(self, admin):
        # After TestFundingSources we created 50000 principal + 5000 repayment.
        # And TestExpenses.eid amount=1300 (post-update).
        j = admin.get(f"{BASE_URL}/api/finance/summary").json()
        # capital_received >= 50000, capital_repaid >= 5000
        assert j["capital_received"] >= 50000
        assert j["capital_repaid"] >= 5000
        # capital_outstanding = capital_received - capital_repaid
        assert abs(j["capital_outstanding"] - (j["capital_received"] - j["capital_repaid"])) < 0.01
        # expenses_total should be > 0
        assert j["expenses_total"] >= 1300

    def test_expenses_by_category_shape(self, admin):
        j = admin.get(f"{BASE_URL}/api/finance/summary").json()
        for entry in j["expenses_by_category"]:
            assert "category" in entry and "amount" in entry
            assert isinstance(entry["amount"], (int, float))


# -------- Treasury report --------
class TestTreasuryReport:
    def test_treasury_json(self, admin):
        r = admin.get(f"{BASE_URL}/api/reports/v2/treasury")
        assert r.status_code == 200, r.text
        j = r.json()
        assert "kpis" in j and "columns" in j and "rows" in j
        for k in ("capital_received", "capital_outstanding", "expenses_total", "expense_categories"):
            assert k in j["kpis"], f"missing kpi {k}"

    def test_treasury_xlsx(self, admin):
        r = admin.get(f"{BASE_URL}/api/reports/v2/treasury/export", params={"format": "xlsx"})
        assert r.status_code == 200
        assert "openxmlformats" in r.headers.get("content-type", "")
        assert r.content[:2] == b"PK"

    def test_treasury_pdf_branded(self, admin):
        r = admin.get(f"{BASE_URL}/api/reports/v2/treasury/export", params={"format": "pdf"})
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 30 * 1024, f"pdf too small: {len(r.content)} bytes"


# -------- WhatsApp branding in PDFs --------
class TestWhatsAppBrandingPDF:
    """Extract text from a generated PDF and ensure 'WhatsApp: +670 78372678' appears."""

    def _extract_text(self, pdf_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader  # type: ignore
            except ImportError:
                pytest.skip("pypdf/PyPDF2 not available")
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((p.extract_text() or "") for p in reader.pages)

    def test_report_pdf_has_whatsapp(self, admin):
        r = admin.get(f"{BASE_URL}/api/reports/v2/financial/export", params={"format": "pdf"})
        assert r.status_code == 200
        text = self._extract_text(r.content)
        # Be flexible with spacing — pdf text extraction may collapse spaces
        normalized = re.sub(r"\s+", "", text)
        assert "WhatsApp" in text or "WhatsApp" in normalized
        assert "78372678" in normalized

    def test_treasury_pdf_has_whatsapp(self, admin):
        r = admin.get(f"{BASE_URL}/api/reports/v2/treasury/export", params={"format": "pdf"})
        text = self._extract_text(r.content)
        normalized = re.sub(r"\s+", "", text)
        assert "WhatsApp" in text
        assert "78372678" in normalized


# -------- Cleanup of funding source at end --------
class TestZCleanup:
    def test_delete_funding_source(self, admin):
        sid = TestFundingSources.src_id
        if not sid:
            pytest.skip("no source to delete")
        r = admin.delete(f"{BASE_URL}/api/funding-sources/{sid}")
        assert r.status_code in (200, 204), r.text
        # repayments should be gone too
        reps = admin.get(f"{BASE_URL}/api/funding-sources/{sid}/repayments")
        # 200 with [] is acceptable since list endpoint doesn't 404
        if reps.status_code == 200:
            assert reps.json() == []

    def test_delete_expense(self, admin):
        eid = TestExpenses.eid
        if not eid:
            pytest.skip("no expense")
        r = admin.delete(f"{BASE_URL}/api/expenses/{eid}")
        assert r.status_code in (200, 204)
