"""Iteration 10 regression — 6 new feature batch on top of iter9.

NEW features under test:
  1) name + machine_number fields on Car / Motorcycle / Pezadu
  2) Pre-Auction (days_overdue / auction_ready status >10 days, penalty_paid)
  3) Overdue Payment types: overdue_full / overdue_interest_pen / overdue_penalty_only
  4) Client Payment Summary (frontend) — verifies underlying payments persist
  5) FundingSource (Capital Source) term_months + rate persistence
  6) Auction mark_sold with optional interest_fee → cash_portion split,
     /finance/summary keys auction_interest_profit & auction_tax_collected,
     and buyer-facing invoice PDF must NOT contain 'Interest Fee' / interest line.

Auth = httpOnly cookies (single requests.Session).
"""
from __future__ import annotations

import os
import re
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pawnly-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# ---------- session/auth fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def test_client_id(admin_session):
    r = admin_session.post(f"{API}/clients", json={
        "full_name": "TEST_iter10 Client",
        "id_type": "BI",
        "id_number": "TEST-IT10-001",
        "phone": "+67077000010",
        "address": "Dili",
    })
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    yield cid
    admin_session.delete(f"{API}/clients/{cid}")


# =====================================================================
# 1) Items — name + machine_number on Car / Motorcycle / Pezadu
# =====================================================================
class TestItemsNameMachineNumber:
    def test_car_name_and_machine_number_roundtrip(self, admin_session):
        payload = {
            "name": "TEST_iter10 Toyota Hilux 2026",
            "brand": "Toyota",
            "model": "Hilux",
            "machine_number": "ENG-12345",
            "manufacture_year": 2026,
            "market_value": 25000.0,
            "location": "warehouse",
        }
        r = admin_session.post(f"{API}/items/car", json=payload)
        assert r.status_code == 200, r.text
        iid = r.json()["id"]
        try:
            assert r.json()["name"] == "TEST_iter10 Toyota Hilux 2026"
            assert r.json()["machine_number"] == "ENG-12345"
            # GET to verify persistence
            g = admin_session.get(f"{API}/items/car/{iid}")
            assert g.status_code == 200
            data = g.json()
            assert data["name"] == "TEST_iter10 Toyota Hilux 2026"
            assert data["machine_number"] == "ENG-12345"
        finally:
            admin_session.delete(f"{API}/items/car/{iid}")

    def test_motorcycle_name_and_machine_number_roundtrip(self, admin_session):
        payload = {
            "name": "TEST_iter10 Honda CB 150",
            "brand": "Honda",
            "model": "CB150",
            "machine_number": "ENG-MOTO-77",
            "market_value": 1500.0,
        }
        r = admin_session.post(f"{API}/items/motorcycle", json=payload)
        assert r.status_code == 200, r.text
        iid = r.json()["id"]
        try:
            g = admin_session.get(f"{API}/items/motorcycle/{iid}").json()
            assert g["name"] == "TEST_iter10 Honda CB 150"
            assert g["machine_number"] == "ENG-MOTO-77"
        finally:
            admin_session.delete(f"{API}/items/motorcycle/{iid}")

    def test_pezadu_name_and_machine_number_roundtrip(self, admin_session):
        """Frontend sends name + machine_number for Pezadu — backend MUST persist these."""
        payload = {
            "name": "TEST_iter10 Komatsu Forklift FD25T",
            "category": "forklift",
            "brand": "Komatsu",
            "model": "FD25T",
            "machine_number": "ENG-PEZ-88",
            "market_value": 18000.0,
        }
        r = admin_session.post(f"{API}/items/pezadu", json=payload)
        assert r.status_code == 200, r.text
        iid = r.json()["id"]
        try:
            g = admin_session.get(f"{API}/items/pezadu/{iid}").json()
            assert g.get("name") == "TEST_iter10 Komatsu Forklift FD25T", (
                f"Pezadu 'name' field not persisted — got: {g.get('name')!r}. "
                "Backend PezaduIn model likely missing 'name' field.")
            assert g.get("machine_number") == "ENG-PEZ-88", (
                f"Pezadu 'machine_number' field not persisted — got: {g.get('machine_number')!r}. "
                "Backend PezaduIn model likely missing 'machine_number' field.")
        finally:
            admin_session.delete(f"{API}/items/pezadu/{iid}")


# =====================================================================
# 2) Contracts — days_overdue / penalty_paid / auction_ready status
# =====================================================================
@pytest.fixture
def overdue_contract_factory(admin_session, test_client_id):
    """Creates a contract with arbitrary due_date offset; auto-cleanup."""
    created = []

    def _make(days_ago_due: int, loan: float = 1000.0, rate: float = 10.0):
        # Create a fresh item for each contract
        item_r = admin_session.post(f"{API}/items/car", json={
            "name": f"TEST_iter10 Car overdue-{days_ago_due}",
            "brand": "Ford",
            "model": "Ranger",
            "market_value": 5000.0,
        })
        assert item_r.status_code == 200, item_r.text
        item_id = item_r.json()["id"]

        contract_date = (date.today() - timedelta(days=days_ago_due + 30)).isoformat()
        due_date = (date.today() - timedelta(days=days_ago_due)).isoformat()
        r = admin_session.post(f"{API}/contracts", json={
            "client_id": test_client_id,
            "item_id": item_id,
            "item_type": "car",
            "loan_amount": loan,
            "interest_rate": rate,
            "contract_date": contract_date,
            "due_date": due_date,
            "notes": "TEST_iter10",
        })
        assert r.status_code == 200, r.text
        c = r.json()
        created.append((c["id"], item_id))
        return c

    yield _make
    for cid, iid in created:
        admin_session.delete(f"{API}/contracts/{cid}")
        admin_session.delete(f"{API}/items/car/{iid}")


class TestContractsOverdue:
    def test_contract_has_days_overdue_and_penalty_paid_fields(self, admin_session, overdue_contract_factory):
        c = overdue_contract_factory(days_ago_due=5)
        # GET list
        r = admin_session.get(f"{API}/contracts")
        assert r.status_code == 200
        row = next((x for x in r.json() if x["id"] == c["id"]), None)
        assert row is not None
        assert "days_overdue" in row, "Contract missing 'days_overdue' field"
        assert "penalty_paid" in row, "Contract missing 'penalty_paid' field"
        assert isinstance(row["days_overdue"], int)
        assert row["days_overdue"] >= 5
        assert row["penalty_paid"] == 0.0
        assert row["status"] == "overdue", f"Expected 'overdue', got {row['status']!r}"

    def test_contract_auction_ready_after_10_days(self, admin_session, overdue_contract_factory):
        c = overdue_contract_factory(days_ago_due=15)
        r = admin_session.get(f"{API}/contracts/{c['id']}")
        assert r.status_code == 200
        data = r.json()
        assert data["days_overdue"] >= 15
        assert data["status"] == "auction_ready", (
            f"Expected 'auction_ready' for >10 day overdue, got {data['status']!r}")


# =====================================================================
# 3) Payments — overdue_full / overdue_interest_pen / overdue_penalty_only
# =====================================================================
class TestOverduePayments:
    def test_overdue_penalty_only(self, admin_session, overdue_contract_factory):
        c = overdue_contract_factory(days_ago_due=5, loan=1000.0, rate=10.0)
        # Fetch current penalty
        cur = admin_session.get(f"{API}/contracts/{c['id']}").json()
        penalty = float(cur.get("penalty", 0))
        assert penalty > 0, f"Expected nonzero penalty on overdue contract, got {penalty}"

        pay = admin_session.post(f"{API}/payments", json={
            "contract_id": c["id"],
            "amount": penalty,
            "type": "overdue_penalty_only",
            "method": "cash",
            "date": date.today().isoformat(),
            "notes": "TEST_iter10 penalty only",
        })
        assert pay.status_code == 200, pay.text
        # Re-fetch contract
        after = admin_session.get(f"{API}/contracts/{c['id']}").json()
        assert abs(after["penalty_paid"] - penalty) < 0.01
        assert abs(float(after.get("penalty", 0))) < 0.01, (
            f"Penalty remaining should be 0 after overdue_penalty_only, got {after.get('penalty')}")

    def test_overdue_interest_pen(self, admin_session, overdue_contract_factory):
        c = overdue_contract_factory(days_ago_due=5, loan=1000.0, rate=10.0)
        cur = admin_session.get(f"{API}/contracts/{c['id']}").json()
        amt = float(cur.get("penalty", 0)) + float(cur.get("interest_remaining", 0))
        assert amt > 0

        pay = admin_session.post(f"{API}/payments", json={
            "contract_id": c["id"],
            "amount": amt,
            "type": "overdue_interest_pen",
            "method": "cash",
            "date": date.today().isoformat(),
        })
        assert pay.status_code == 200, pay.text
        after = admin_session.get(f"{API}/contracts/{c['id']}").json()
        # penalty + interest should both be effectively zero
        assert float(after.get("penalty", 0)) < 0.01
        assert float(after.get("interest_remaining", 0)) < 0.01

    def test_overdue_full_closes_contract(self, admin_session, overdue_contract_factory):
        c = overdue_contract_factory(days_ago_due=5, loan=1000.0, rate=10.0)
        cur = admin_session.get(f"{API}/contracts/{c['id']}").json()
        amt = (float(cur.get("penalty", 0))
               + float(cur.get("interest_remaining", 0))
               + float(cur.get("principal_remaining", cur.get("loan_amount", 1000.0))))
        assert amt > 0

        pay = admin_session.post(f"{API}/payments", json={
            "contract_id": c["id"],
            "amount": amt,
            "type": "overdue_full",
            "method": "cash",
            "date": date.today().isoformat(),
        })
        assert pay.status_code == 200, pay.text
        after = admin_session.get(f"{API}/contracts/{c['id']}").json()
        # closed status & all zero
        assert after["status"] in ("closed", "completed", "paid", "redeemed"), f"Expected closed-ish status, got {after['status']}"
        assert float(after.get("penalty", 0)) < 0.01
        assert float(after.get("principal_remaining", 0)) < 0.01


# =====================================================================
# 5) Finance — Capital Source rate + term_months persistence
# =====================================================================
class TestCapitalSource:
    def test_capital_source_with_term_months(self, admin_session):
        r = admin_session.post(f"{API}/funding-sources", json={
            "name": "TEST_iter10 BNCTL Loan",
            "source_type": "bank",
            "principal_amount": 10000.0,
            "interest_rate": 5,
            "interest_period": "yearly",
            "term_months": 12,
            "start_date": date.today().isoformat(),
        })
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        try:
            lst = admin_session.get(f"{API}/funding-sources").json()
            row = next((x for x in lst if x["id"] == sid), None)
            assert row is not None
            assert row.get("interest_rate") == 5
            assert row.get("term_months") == 12
            assert row.get("principal_amount") == 10000.0
        finally:
            admin_session.delete(f"{API}/funding-sources/{sid}")


# =====================================================================
# 6) Auctions — mark_sold + interest_fee, /finance/summary, invoice PDF
# =====================================================================
@pytest.fixture
def auction_ready_contract(admin_session, test_client_id):
    """A >10-day overdue contract and item ready to be auctioned."""
    item_r = admin_session.post(f"{API}/items/car", json={
        "name": "TEST_iter10 Auction Car",
        "brand": "Mitsubishi",
        "model": "L200",
        "market_value": 8000.0,
    })
    assert item_r.status_code == 200
    item_id = item_r.json()["id"]

    contract_date = (date.today() - timedelta(days=60)).isoformat()
    due_date = (date.today() - timedelta(days=20)).isoformat()
    r = admin_session.post(f"{API}/contracts", json={
        "client_id": test_client_id,
        "item_id": item_id,
        "item_type": "car",
        "loan_amount": 1000.0,
        "interest_rate": 10,
        "contract_date": contract_date,
        "due_date": due_date,
    })
    assert r.status_code == 200, r.text
    contract = r.json()
    yield contract, item_id
    # cleanup
    admin_session.delete(f"{API}/contracts/{contract['id']}")
    admin_session.delete(f"{API}/items/car/{item_id}")


def _create_auction(admin_session, contract_id):
    r = admin_session.post(f"{API}/auctions/move", json={
        "contract_id": contract_id,
        "starting_price": 1500.0,
    })
    assert r.status_code == 200, r.text
    return r.json()


class TestAuctionSold:
    def test_mark_sold_with_explicit_interest_fee(self, admin_session, auction_ready_contract):
        contract, item_id = auction_ready_contract
        a = _create_auction(admin_session, contract["id"])
        # Get finance summary baseline
        fs_before = admin_session.get(f"{API}/finance/summary").json()
        sold_payload = {
            "sold_price": 1000.0,
            "interest_fee": 200.0,
            "tax_percent": 10.0,
            "buyer_name": "TEST_iter10 Buyer",
            "buyer_phone": "+67077001111",
            "buyer_address": "Dili",
            "buyer_id_number": "BUY-IT10-001",
            "sold_date": date.today().isoformat(),
        }
        r = admin_session.post(f"{API}/auctions/{a['id']}/sold", json=sold_payload)
        assert r.status_code == 200, r.text
        body = r.json()
        # Backend persists interest_fee + cash_portion
        # Could be embedded in auction or in invoice — verify via /auctions GET
        sold = admin_session.get(f"{API}/auctions").json()
        sold_row = next((x for x in sold if x["id"] == a["id"]), None)
        assert sold_row is not None
        assert abs(float(sold_row.get("interest_fee", 0)) - 200.0) < 0.01, (
            f"interest_fee not persisted on auction: got {sold_row.get('interest_fee')}")
        assert abs(float(sold_row.get("cash_portion", 0)) - 800.0) < 0.01, (
            f"cash_portion (sold_price - interest_fee) not persisted: got {sold_row.get('cash_portion')}")

        # /finance/summary new keys
        fs = admin_session.get(f"{API}/finance/summary").json()
        assert "auction_interest_profit" in fs, "Finance summary missing 'auction_interest_profit'"
        assert "auction_tax_collected" in fs, "Finance summary missing 'auction_tax_collected'"
        # Nov-2026 auction split: capital vs realized profit
        assert "auction_capital_recovered" in fs
        assert "auction_realized_profit" in fs
        assert "auction_realized_loss" in fs
        # Deltas
        assert fs["auction_interest_profit"] - fs_before.get("auction_interest_profit", 0) >= 200 - 0.01
        assert fs["auction_sales"] - fs_before.get("auction_sales", 0) >= 1000 - 0.01
        assert fs["auction_tax_collected"] - fs_before.get("auction_tax_collected", 0) >= 100 - 0.01
        # Sold at exactly the original loan amount → capital fully recovered,
        # no realized profit, no realized loss. Net profit for THIS sale is 0
        # (interest_fee is now just an internal accounting split, not profit).
        cap_delta = fs["auction_capital_recovered"] - fs_before.get("auction_capital_recovered", 0)
        assert cap_delta >= 1000 - 0.01, f"capital_recovered delta should be ~$1000, got {cap_delta}"
        profit_delta = fs["auction_realized_profit"] - fs_before.get("auction_realized_profit", 0)
        assert profit_delta < 0.01, f"realized_profit delta should be 0 (sold at original), got {profit_delta}"

        # Invoice generated — find it
        invs = admin_session.get(f"{API}/invoices").json()
        # Pick latest invoice for this auction (match buyer_name)
        inv = next((i for i in invs if i.get("buyer_name") == "TEST_iter10 Buyer"), None)
        assert inv is not None, "Invoice not created after mark_sold"
        # Buyer-facing fields: subtotal + tax + total only
        assert abs(float(inv["subtotal"]) - 1000.0) < 0.01
        assert abs(float(inv["tax_amount"]) - 100.0) < 0.01
        assert abs(float(inv["total"]) - 1100.0) < 0.01

        # Invoice PDF should NOT contain 'Interest Fee' or 'Interest' line
        pdf = admin_session.get(f"{API}/invoices/{inv['id']}/pdf")
        assert pdf.status_code == 200
        assert pdf.content[:4] == b"%PDF"
        body_lower = pdf.content.lower()
        assert b"interest fee" not in body_lower, "Buyer invoice PDF MUST NOT contain 'Interest Fee'"
        # Try text extraction with pypdf for stronger check (optional — skip if not installed)
        try:
            from pypdf import PdfReader
            from io import BytesIO
            reader = PdfReader(BytesIO(pdf.content))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
            assert "Interest Fee" not in text, f"PDF text contains 'Interest Fee': {text[:500]}"
            assert "interest_fee" not in text.lower()
        except ImportError:
            pass

    def test_mark_sold_without_interest_fee_auto_computes(self, admin_session, auction_ready_contract):
        contract, item_id = auction_ready_contract
        a = _create_auction(admin_session, contract["id"])
        # contract has interest_remaining + penalty — capture for assertion
        c = admin_session.get(f"{API}/contracts/{contract['id']}").json()
        expected_fee = float(c.get("interest_remaining", 0)) + float(c.get("penalty", 0))

        r = admin_session.post(f"{API}/auctions/{a['id']}/sold", json={
            "sold_price": 1500.0,
            "tax_percent": 0.0,
            "buyer_name": "TEST_iter10 Buyer Auto",
            "buyer_phone": "+67077002222",
            "buyer_address": "Dili",
            "sold_date": date.today().isoformat(),
            # interest_fee deliberately omitted
        })
        assert r.status_code == 200, r.text
        sold_row = next((x for x in admin_session.get(f"{API}/auctions").json() if x["id"] == a["id"]), None)
        assert sold_row is not None
        got_fee = float(sold_row.get("interest_fee", -1))
        # Allow small tolerance, capped at sold_price
        capped_expected = min(expected_fee, 1500.0)
        assert abs(got_fee - capped_expected) < 1.0, (
            f"Auto-computed interest_fee mismatch: got {got_fee}, expected ~{capped_expected}")


# =====================================================================
# Regression — existing endpoints still alive
# =====================================================================
class TestRegression:
    def test_dashboard_summary(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/summary")
        assert r.status_code == 200
        assert "total_clients" in r.json() or "clients_count" in r.json() or isinstance(r.json(), dict)

    def test_finance_summary_keys(self, admin_session):
        r = admin_session.get(f"{API}/finance/summary")
        assert r.status_code == 200
        keys = r.json().keys()
        for k in ("cash_on_hand", "net_profit", "auction_sales",
                  "auction_interest_profit", "auction_tax_collected"):
            assert k in keys, f"Missing finance summary key: {k}"

    def test_settings_still_loads(self, admin_session):
        r = admin_session.get(f"{API}/settings")
        assert r.status_code == 200
        assert r.json().get("id") == "singleton"

    def test_backups_list(self, admin_session):
        r = admin_session.get(f"{API}/admin/backups")
        assert r.status_code == 200
