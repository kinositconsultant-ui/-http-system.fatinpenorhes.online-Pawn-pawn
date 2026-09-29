"""Iter 83 — Cash Drawer + Closed Contracts export + Auction-day reminder preview + Receipt quote block.

Covers:
  1. GET/PUT /api/settings next_auction_date roundtrip
  2. GET /api/subscribers/auction-day-reminder/preview (401 unauth, admin ok, no-date + with-date bodies)
  3. POST /api/subscribers/auction-day-reminder/test (422 short phone; success 'mocked' with valid phone)
  4. GET /api/business/closed-contracts / export/pdf / export/csv (headers, TOTAL row)
  5. GET /api/finance/cash-drawer + /export/pdf (identity totals; overpayment toggle flow)
  6. GET /api/payments/{id}/pdf — quote block appears for interest_only/partial on active, absent on 'full'
  7. Regression sanity: DELETE /api/payments/{id} cleanup

Cleans up: restores next_auction_date to '' and deletes any TEST payment.
"""
from __future__ import annotations

import io
import os
import time
from datetime import date

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PWD = "admin123"


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    yield s
    # Restore next_auction_date to empty at end of module
    try:
        s.put(f"{BASE_URL}/api/settings", json={"next_auction_date": ""})
    except Exception:
        pass


@pytest.fixture(scope="module")
def anon_client():
    return requests.Session()


# ---------------------------------------------------------------------
# Auction-day reminder preview + test-send
# ---------------------------------------------------------------------
class TestAuctionReminder:
    def test_preview_unauth_401(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/subscribers/auction-day-reminder/preview")
        assert r.status_code == 401

    def test_preview_no_date(self, admin_client):
        # Ensure it's cleared first
        admin_client.put(f"{BASE_URL}/api/settings", json={"next_auction_date": ""})
        r = admin_client.get(f"{BASE_URL}/api/subscribers/auction-day-reminder/preview")
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        # When no date: next_auction_date should be empty / falsy
        assert not (data.get("next_auction_date") or "").strip(), (
            f"expected empty next_auction_date, got: {data.get('next_auction_date')}")

    def test_set_date_and_preview_body(self, admin_client):
        put = admin_client.put(f"{BASE_URL}/api/settings", json={"next_auction_date": "2026-10-15"})
        assert put.status_code == 200
        r = admin_client.get(f"{BASE_URL}/api/subscribers/auction-day-reminder/preview")
        assert r.status_code == 200
        data = r.json()
        assert data.get("next_auction_date") == "2026-10-15"
        # Send-on = the day before
        assert data.get("send_on") == "2026-10-14"
        body = data.get("body") or ""
        assert "2026-10-15" in body, f"body missing auction date: {body[:300]}"
        # Location should include Caicoli (Tetum body)
        assert "Caicoli" in body, f"body missing 'Caicoli': {body[:300]}"
        # Should mention 09:00 (auction start time)
        assert "09:00" in body, f"body missing '09:00': {body[:300]}"
        # recipients is present (int)
        assert isinstance(data.get("recipients"), int)

    def test_test_send_short_phone_422(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/subscribers/auction-day-reminder/test", json={"phone": "12"})
        assert r.status_code == 422, r.text[:200]

    def test_test_send_valid_phone_mocked(self, admin_client):
        # Set a date so status != 'skipped'
        admin_client.put(f"{BASE_URL}/api/settings", json={"next_auction_date": "2026-10-15"})
        r = admin_client.post(f"{BASE_URL}/api/subscribers/auction-day-reminder/test",
                              json={"phone": "+670 7777 1234"})
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        # WhatsApp not configured → mocked
        assert data.get("status") in ("mocked", "sent"), f"unexpected status: {data}"


# ---------------------------------------------------------------------
# Closed contracts export (Business Dashboard)
# ---------------------------------------------------------------------
class TestClosedContractsExport:
    def test_json(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/business/closed-contracts", params={"month": "2026-09"})
        assert r.status_code == 200
        d = r.json()
        assert d.get("month") == "2026-09"
        assert "rows" in d and "count" in d

    def test_pdf(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/business/closed-contracts/export/pdf", params={"month": "2026-09"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:5] == b"%PDF-", "response is not a PDF file"

    def test_csv_has_header_and_total(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/business/closed-contracts/export/csv", params={"month": "2026-09"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        text = r.text
        assert "Contract" in text and "Client" in text and "Interest earned" in text
        assert "TOTAL" in text, "CSV should contain TOTAL row"


# ---------------------------------------------------------------------
# Cash drawer — daily view + overpayment toggle
# ---------------------------------------------------------------------
class TestCashDrawer:
    def test_get_today(self, admin_client):
        today = date.today().isoformat()
        r = admin_client.get(f"{BASE_URL}/api/finance/cash-drawer", params={"date": today})
        assert r.status_code == 200
        d = r.json()
        assert d["date"] == today
        assert "rows" in d
        t = d["totals"]
        for k in ("cash_in", "change_owed", "change_returned", "change_pending",
                  "disbursed_out", "net_drawer", "receipts", "pending_count"):
            assert k in t, f"missing totals key: {k}"
        # Identity: net_drawer == cash_in - change_returned - disbursed_out
        expected = round(t["cash_in"] - t["change_returned"] - t["disbursed_out"], 2)
        assert abs(t["net_drawer"] - expected) < 0.01, (
            f"net_drawer identity broken: net={t['net_drawer']} vs expected={expected}")

    def test_export_pdf(self, admin_client):
        today = date.today().isoformat()
        r = admin_client.get(f"{BASE_URL}/api/finance/cash-drawer/export/pdf", params={"date": today})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:5] == b"%PDF-"

    def test_overpayment_flow_and_toggle(self, admin_client):
        """Create an interest_only overpayment on any active contract → row appears in cash drawer
        with 'Pending' change, toggle to returned, verify totals shift, then delete payment."""
        # Find any active contract
        r = admin_client.get(f"{BASE_URL}/api/contracts")
        assert r.status_code == 200
        contracts = r.json()
        active = [c for c in contracts if c.get("status") in ("active", "grace_period")]
        if not active:
            pytest.skip("No active contract to test overpayment against")
        c = active[0]
        cid = c["id"]

        # Get contract details to find total_due; use `partial` with amount > total_due to force overpaid
        cd = admin_client.get(f"{BASE_URL}/api/contracts/{cid}")
        assert cd.status_code == 200
        cinfo = cd.json()
        total_due = float(cinfo.get("total_due") or cinfo.get("remaining_balance") or 0)
        if total_due <= 0:
            pytest.skip("selected contract has no outstanding balance")
        pay_amount = round(total_due + 5.0, 2)

        today = date.today().isoformat()
        cr = admin_client.post(f"{BASE_URL}/api/payments", json={
            "contract_id": cid,
            "amount": pay_amount,
            "type": "partial",
            "date": today,
            "notes": "TEST_iter83_overpay",
        })
        assert cr.status_code == 200, f"create payment failed: {cr.status_code} {cr.text[:300]}"
        pay = cr.json().get("payment") or {}
        pid = pay.get("id")
        overpaid = float(pay.get("overpaid") or 0)
        assert pid, "no payment id returned"
        try:
            assert overpaid > 0, f"expected overpaid > 0, got {overpaid}. resp={cr.json()}"

            # Check cash drawer shows this row w/ change pending
            dr = admin_client.get(f"{BASE_URL}/api/finance/cash-drawer", params={"date": today})
            assert dr.status_code == 200
            drawer = dr.json()
            row = next((x for x in drawer["rows"] if x["id"] == pid), None)
            assert row is not None, "new payment not in cash-drawer rows"
            assert row["overpaid"] > 0
            assert row["change_returned"] is False
            totals_before = drawer["totals"]
            pending_before = totals_before["change_pending"]
            returned_before = totals_before["change_returned"]
            assert pending_before > 0

            # Toggle change-returned = true
            tog = admin_client.post(f"{BASE_URL}/api/payments/{pid}/change-returned",
                                    params={"returned": "true"})
            assert tog.status_code == 200, tog.text[:200]
            assert tog.json().get("change_returned") is True

            # Verify totals shift
            dr2 = admin_client.get(f"{BASE_URL}/api/finance/cash-drawer", params={"date": today})
            drawer2 = dr2.json()
            totals_after = drawer2["totals"]
            row2 = next((x for x in drawer2["rows"] if x["id"] == pid), None)
            assert row2 and row2["change_returned"] is True
            assert totals_after["change_pending"] < pending_before - 0.001, (
                f"change_pending did not decrease: {pending_before} -> {totals_after['change_pending']}")
            assert totals_after["change_returned"] > returned_before - 0.001

            # Toggle back
            tog2 = admin_client.post(f"{BASE_URL}/api/payments/{pid}/change-returned",
                                     params={"returned": "false"})
            assert tog2.status_code == 200
            assert tog2.json().get("change_returned") is False

            # ---- Receipt PDF should contain 'Pay Today vs Next Month' block for interest_only/partial + active
            # If our partial payment fully cleared and redeemed the contract, skip this assertion.
            contract_after = admin_client.get(f"{BASE_URL}/api/contracts/{cid}").json()
            if contract_after.get("status") != "redeemed":
                pdf = admin_client.get(f"{BASE_URL}/api/payments/{pid}/pdf")
                assert pdf.status_code == 200
                assert pdf.content[:5] == b"%PDF-"
                body = pdf.content
                found_quote_block = (b"Pay Today vs Next Month" in body
                                     or b"Pay Today" in body
                                     or b"Next Month" in body)
                assert found_quote_block, "quote block markers not found in partial receipt PDF"
        finally:
            # Cleanup
            d = admin_client.delete(f"{BASE_URL}/api/payments/{pid}")
            assert d.status_code == 200, f"cleanup delete failed: {d.status_code} {d.text[:200]}"


# ---------------------------------------------------------------------
# Receipt PDF absence-of-quote for 'full' payment (redeemed)
# ---------------------------------------------------------------------
class TestReceiptQuoteAbsentOnFull:
    def test_full_payment_receipt_no_quote_block(self, admin_client):
        """Find an existing 'full' or 'overdue_full' payment on a redeemed contract and
        verify the quote block is absent."""
        r = admin_client.get(f"{BASE_URL}/api/payments")
        if r.status_code != 200:
            pytest.skip("payments list unavailable")
        pays = r.json()
        full = [p for p in pays if p.get("type") in ("full", "overdue_full")]
        if not full:
            pytest.skip("no full/overdue_full payment in system")
        # Pick the first one whose contract is redeemed
        for p in full[:20]:
            c = admin_client.get(f"{BASE_URL}/api/contracts/{p['contract_id']}")
            if c.status_code != 200:
                continue
            if c.json().get("status") == "redeemed":
                pdf = admin_client.get(f"{BASE_URL}/api/payments/{p['id']}/pdf")
                assert pdf.status_code == 200
                body = pdf.content
                # 'Pay Today vs Next Month' should NOT appear on a full/redeemed receipt
                assert b"Pay Today vs Next Month" not in body, (
                    "quote block should not appear on full-payment redeemed-contract receipt")
                return
        pytest.skip("no redeemed contract with full payment found")
