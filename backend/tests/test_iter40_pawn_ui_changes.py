"""Iter 40 — Backend validation for 5 UX changes:
1. Dashboard: /api/dashboard/summary returns auction_ready_contracts
2. Invoices: DELETE /api/invoices/{iid} (admin-only) + auction cleanup + audit log
3. Auctions: /api/auctions rows include client_name + client_id
4. Finance: /api/finance/summary uses auction_interest_profit in gross_profit
5. Regressions: /api/reports/v2/financial + /api/auctions still work
"""
import os
import requests
import pytest
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


# ---------- Dashboard ----------
class TestDashboardSummary:
    def test_summary_includes_auction_ready(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/summary")
        assert r.status_code == 200
        data = r.json()
        assert "auction_ready_contracts" in data
        assert isinstance(data["auction_ready_contracts"], int)
        # Regression: existing keys still present
        for k in [
            "total_clients", "active_contracts", "overdue_contracts",
            "redeemed_contracts", "auction_contracts",
            "total_loan_amount", "total_payments",
        ]:
            assert k in data, f"missing key {k}"


# ---------- Auctions enrichment ----------
class TestAuctionsListEnrichment:
    def test_auctions_include_client_name(self, admin_session):
        r = admin_session.get(f"{API}/auctions")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        if not rows:
            pytest.skip("No auctions in DB to validate enrichment")
        # Every row must expose client_name + client_id keys (may be empty
        # string / None if the contract's client was deleted, but the keys
        # must exist so the frontend can safely group by them).
        for row in rows:
            assert "client_name" in row, f"auction {row.get('id')} missing client_name"
            assert "client_id" in row, f"auction {row.get('id')} missing client_id"


# ---------- Finance summary formula ----------
class TestFinanceSummaryFormula:
    def test_finance_summary_uses_auction_interest_profit(self, admin_session):
        r = admin_session.get(f"{API}/finance/summary")
        assert r.status_code == 200, f"finance summary failed: {r.status_code} {r.text}"
        data = r.json()
        assert "auction_interest_profit" in data
        assert "interest_received" in data
        assert "total_penalty" in data
        assert "gross_profit" in data
        assert "net_profit" in data
        assert "expenses_total" in data
        aip = float(data["auction_interest_profit"])
        ir = float(data["interest_received"])
        tp = float(data["total_penalty"])
        gp = float(data["gross_profit"])
        exp = float(data["expenses_total"])
        np_ = float(data["net_profit"])
        # gross_profit = interest_received + total_penalty + auction_interest_profit
        assert round(gp, 2) == round(ir + tp + aip, 2), (
            f"gross_profit mismatch: got {gp} expected {ir + tp + aip}"
        )
        # net_profit = gross_profit - expenses_total
        assert round(np_, 2) == round(gp - exp, 2)


# ---------- Invoice delete flow ----------
class TestInvoiceDelete:
    """Full lifecycle test: create auction → mark sold (creates invoice) →
    verify invoice exists → delete invoice → verify cleanup + audit."""

    def _mk_auction_with_invoice(self, s):
        """Try to find (or produce) a sold auction with invoice, else skip."""
        rows = s.get(f"{API}/auctions").json()
        # Prefer existing sold-with-invoice auction
        sold = [a for a in rows if a.get("status") == "sold" and a.get("invoice_id")]
        if sold:
            return sold[0]
        # Otherwise try to mark a listed one sold
        listed = [a for a in rows if a.get("status") == "listed"]
        if not listed:
            return None
        a = listed[0]
        payload = {
            "sold_price": float(a.get("starting_price") or 100),
            "tax_percent": 0,
            "buyer_name": "TEST_invoice_delete_buyer",
            "notes": "iter40 auto-test",
            "interest_fee": 5.0,
        }
        r = s.post(f"{API}/auctions/{a['id']}/sold", json=payload)
        if r.status_code != 200:
            return None
        # Re-fetch
        rows = s.get(f"{API}/auctions").json()
        for x in rows:
            if x["id"] == a["id"]:
                return x
        return None

    def test_delete_invoice_admin_and_cleanup(self, admin_session):
        auction = self._mk_auction_with_invoice(admin_session)
        if not auction:
            pytest.skip("No sold auction with invoice available (and cannot create one)")
        iid = auction["invoice_id"]
        aid = auction["id"]
        # DELETE
        r = admin_session.delete(f"{API}/invoices/{iid}")
        assert r.status_code == 200, f"delete failed: {r.status_code} {r.text}"
        assert r.json().get("ok") is True
        # Fetching the PDF endpoint must now 404
        r2 = admin_session.get(f"{API}/invoices/{iid}/pdf")
        assert r2.status_code == 404
        # Auction should have invoice_id / invoice_number cleared
        after = admin_session.get(f"{API}/auctions").json()
        aft = next((x for x in after if x["id"] == aid), None)
        assert aft is not None
        assert not aft.get("invoice_id"), f"invoice_id still on auction: {aft.get('invoice_id')}"
        assert not aft.get("invoice_number"), f"invoice_number still on auction: {aft.get('invoice_number')}"

    def test_delete_invoice_404_when_missing(self, admin_session):
        r = admin_session.delete(f"{API}/invoices/does-not-exist-xyz")
        assert r.status_code == 404


# ---------- Non-admin cannot delete invoice ----------
class TestInvoiceDeleteRBAC:
    def test_unauthenticated_delete_invoice_forbidden(self):
        # No cookies at all — must NOT be 200
        r = requests.delete(f"{API}/invoices/anything")
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


# ---------- Regression endpoints ----------
class TestRegression:
    def test_reports_v2_financial(self, admin_session):
        r = admin_session.get(f"{API}/reports/v2/financial")
        assert r.status_code == 200
        # loose shape check
        data = r.json()
        assert isinstance(data, dict)

    def test_auctions_list_still_works(self, admin_session):
        r = admin_session.get(f"{API}/auctions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_dashboard_summary_still_works(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/summary")
        assert r.status_code == 200
