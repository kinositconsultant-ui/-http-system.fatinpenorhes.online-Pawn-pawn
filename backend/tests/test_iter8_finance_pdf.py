"""Iteration 8 — Finance PDF exports + Invoices PDFs.

Covers (all with admin cookie session):
- /api/finance/summary/export/pdf (+ month/year filter)
- /api/finance/capital-sources/export/pdf
- /api/finance/expenses/export/pdf (no filter, category filter, month+year filter)
- /api/invoices/export/pdf (list)
- /api/invoices/{id}/pdf (single)
- /api/finance/summary now includes total_invoices + total_invoiced
- Auctions sold-flow auto-creates an Invoice and stores invoice_id

Auth: cookie-based (httpOnly). PDF assertions: content-type starts with
application/pdf, body starts with %PDF, body length > 5KB.
"""
import os
import io
import time
import requests
import pytest
from datetime import date

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _assert_pdf(resp, min_size=5 * 1024):
    assert resp.status_code == 200, f"{resp.status_code} {resp.text[:200]}"
    ct = resp.headers.get("content-type", "")
    assert ct.startswith("application/pdf"), f"unexpected ct={ct}"
    body = resp.content
    assert body[:4] == b"%PDF", f"not a PDF, first bytes: {body[:8]!r}"
    assert len(body) > min_size, f"pdf too small: {len(body)} bytes"


# ---------- Finance Summary PDF ----------
class TestFinanceSummaryPdf:
    def test_summary_includes_invoice_keys(self, admin):
        r = admin.get(f"{BASE_URL}/api/finance/summary")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "total_invoices" in data, list(data.keys())
        assert "total_invoiced" in data, list(data.keys())
        assert isinstance(data["total_invoices"], int)
        assert isinstance(data["total_invoiced"], (int, float))

    def test_summary_pdf_default(self, admin):
        r = admin.get(f"{BASE_URL}/api/finance/summary/export/pdf")
        _assert_pdf(r)

    def test_summary_pdf_with_month_year(self, admin):
        today = date.today()
        r = admin.get(
            f"{BASE_URL}/api/finance/summary/export/pdf",
            params={"month": today.month, "year": today.year},
        )
        _assert_pdf(r)


# ---------- Capital Sources PDF ----------
class TestCapitalSourcesPdf:
    def test_capital_pdf(self, admin):
        r = admin.get(f"{BASE_URL}/api/finance/capital-sources/export/pdf")
        _assert_pdf(r)


# ---------- Expenses PDFs ----------
class TestExpensesPdf:
    @pytest.fixture(scope="class", autouse=True)
    def seed_expenses(self, admin):
        # Seed at least one expense in each tested category so filtered PDF
        # still has something to render. Uses TEST_ prefix in paid_to.
        ts = int(time.time())
        today = date.today().isoformat()
        for cat, amt in [("Salary", 1000), ("Utilities", 200)]:
            admin.post(f"{BASE_URL}/api/expenses", json={
                "category": cat,
                "amount": amt,
                "date": today,
                "paid_to": f"TEST_iter8_{cat}_{ts}",
                "description": "iter8 seed",
            })
        yield

    def test_expenses_pdf_no_filter(self, admin):
        r = admin.get(f"{BASE_URL}/api/finance/expenses/export/pdf")
        _assert_pdf(r)

    def test_expenses_pdf_with_category(self, admin):
        r = admin.get(
            f"{BASE_URL}/api/finance/expenses/export/pdf",
            params={"category": "Salary"},
        )
        _assert_pdf(r)
        cd = r.headers.get("content-disposition", "")
        assert "expenses-Salary.pdf" in cd, cd

    def test_expenses_pdf_with_month_year(self, admin):
        today = date.today()
        r = admin.get(
            f"{BASE_URL}/api/finance/expenses/export/pdf",
            params={"month": today.month, "year": today.year},
        )
        _assert_pdf(r)


# ---------- Invoices (list + single) ----------
class TestInvoicesPdf:
    def test_invoices_list_endpoint(self, admin):
        r = admin.get(f"{BASE_URL}/api/invoices")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_invoices_list_pdf(self, admin):
        r = admin.get(f"{BASE_URL}/api/invoices/export/pdf")
        _assert_pdf(r, min_size=2 * 1024)  # list can be empty -> smaller

    def test_invoice_route_ordering(self, admin):
        """Ensure /invoices/export/pdf is NOT mis-matched as /invoices/{iid}."""
        r = admin.get(f"{BASE_URL}/api/invoices/export/pdf")
        assert r.headers.get("content-type", "").startswith("application/pdf"), \
            "route ordering bug: export/pdf was captured by /{iid}"

    def test_single_invoice_pdf_if_any(self, admin):
        r = admin.get(f"{BASE_URL}/api/invoices")
        invs = r.json()
        if not invs:
            pytest.skip("no invoices in DB yet (sold-flow test below will exercise it)")
        iid = invs[0]["id"]
        rp = admin.get(f"{BASE_URL}/api/invoices/{iid}/pdf")
        _assert_pdf(rp)


# ---------- Sold-auction -> Invoice auto-create ----------
class TestSoldAuctionInvoiceFlow:
    """End-to-end: create client+contract+auction, mark sold, expect invoice."""

    @pytest.fixture(scope="class")
    def sold_invoice(self, admin):
        ts = int(time.time())
        # 1. client
        rc = admin.post(f"{BASE_URL}/api/clients", json={
            "full_name": f"TEST_iter8_client_{ts}",
            "phone": "+670 7000 0000",
            "id_number": f"TEST{ts}",
            "id_type": "BI",
        })
        assert rc.status_code in (200, 201), rc.text
        client_id = rc.json()["id"]

        # 2. item (electronic)
        ri = admin.post(f"{BASE_URL}/api/items/electronic", json={
            "category": "Phone",
            "brand": "TEST",
            "model": f"iter8_{ts}",
            "description": "TEST_iter8 phone",
            "market_value": 200.0,
        })
        if ri.status_code not in (200, 201):
            pytest.fail(f"item create failed: {ri.status_code} {ri.text[:300]}")
        item_id = ri.json()["id"]

        # 3. contract
        from datetime import datetime, timedelta
        start = date.today() - timedelta(days=60)
        due = date.today() - timedelta(days=10)  # overdue
        rk = admin.post(f"{BASE_URL}/api/contracts", json={
            "client_id": client_id,
            "item_id": item_id,
            "item_type": "electronic",
            "loan_amount": 100.0,
            "interest_rate": 10,
            "contract_date": start.isoformat(),
            "due_date": due.isoformat(),
        })
        if rk.status_code not in (200, 201):
            pytest.fail(f"contract create failed: {rk.status_code} {rk.text[:500]}")
        contract = rk.json()
        cid = contract["id"]

        # 4. send to auction
        ra = admin.post(f"{BASE_URL}/api/auctions/move", json={
            "contract_id": cid,
            "starting_price": 150.0,
        })
        if ra.status_code not in (200, 201):
            pytest.fail(f"to-auction failed: {ra.status_code} {ra.text[:300]}")
        aid = ra.json()["id"]

        # 4. mark sold
        rs = admin.post(f"{BASE_URL}/api/auctions/{aid}/sold", json={
            "sold_price": 180.0,
            "buyer_name": f"TEST_iter8_buyer_{ts}",
            "buyer_phone": "+670 7111 0000",
            "tax_percent": 10.0,
        })
        assert rs.status_code in (200, 201), rs.text
        body = rs.json()
        assert body.get("invoice_id"), f"invoice_id missing in sold response: {body}"
        assert body.get("invoice_number", "").startswith("INV-"), body.get("invoice_number")
        return {"auction_id": aid, "invoice_id": body["invoice_id"],
                "invoice_number": body["invoice_number"]}

    def test_invoice_appears_in_list(self, admin, sold_invoice):
        r = admin.get(f"{BASE_URL}/api/invoices")
        ids = [i["id"] for i in r.json()]
        assert sold_invoice["invoice_id"] in ids

    def test_single_invoice_pdf(self, admin, sold_invoice):
        r = admin.get(f"{BASE_URL}/api/invoices/{sold_invoice['invoice_id']}/pdf")
        _assert_pdf(r)
        # invoice number in filename
        cd = r.headers.get("content-disposition", "")
        assert sold_invoice["invoice_number"] in cd, cd

    def test_auction_has_invoice_id(self, admin, sold_invoice):
        r = admin.get(f"{BASE_URL}/api/auctions")
        if r.status_code != 200:
            pytest.skip("auctions list endpoint missing")
        rows = r.json()
        matched = [a for a in rows if a["id"] == sold_invoice["auction_id"]]
        assert matched, "auction missing from list"
        assert matched[0].get("invoice_id") == sold_invoice["invoice_id"]


# ---------- Auth gating ----------
class TestPdfAuth:
    def test_unauth_summary_pdf(self):
        r = requests.get(f"{BASE_URL}/api/finance/summary/export/pdf")
        assert r.status_code in (401, 403), r.status_code

    def test_unauth_invoices_list_pdf(self):
        r = requests.get(f"{BASE_URL}/api/invoices/export/pdf")
        assert r.status_code in (401, 403), r.status_code


# ---------- Regression: existing endpoints still work ----------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/clients",
        "/api/contracts",
        "/api/payments",
        "/api/funding-sources",
        "/api/expenses",
        "/api/auctions",
        "/api/finance/summary",
    ])
    def test_endpoint_ok(self, admin, path):
        r = admin.get(f"{BASE_URL}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
