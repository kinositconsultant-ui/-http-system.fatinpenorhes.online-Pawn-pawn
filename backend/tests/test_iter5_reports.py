"""Iteration 5 backend tests: /api/reports/v2/* endpoints + location field on items."""
import os
import time
import requests
from datetime import date, timedelta

import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
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
def seed(admin):
    """Create at least 1 client, 1 car, 1 motorcycle, 1 electronic with location,
    1 active contract, 1 overdue contract, 1 payment, 1 auction so all reports have data."""
    ts = int(time.time() * 1000)
    # client
    rc = admin.post(f"{API}/clients", json={
        "full_name": f"TEST iter5 {ts}", "id_type": "BI",
        "id_number": f"T5{ts}", "phone": "+670"
    })
    assert rc.status_code == 200, rc.text
    cid = rc.json()["id"]

    # car w/ location
    car = admin.post(f"{API}/items/car", json={
        "brand": "TEST_Toy", "model": "Hilux", "plate": f"T5C{ts}",
        "location": "Warehouse A", "market_value": 5000,
    }).json()
    moto = admin.post(f"{API}/items/motorcycle", json={
        "brand": "TEST_Hon", "model": "PCX",
        "location": "Shop", "market_value": 1500,
    }).json()
    elec = admin.post(f"{API}/items/electronic", json={
        "category": "phone", "brand": "TEST_Sam", "model": "S22",
        "location": "Safe", "market_value": 800,
    }).json()

    today = date.today()
    # active contract on car
    ac = admin.post(f"{API}/contracts", json={
        "client_id": cid, "item_id": car["id"], "item_type": "car",
        "loan_amount": 3000, "interest_rate": 10,
        "contract_date": today.isoformat(),
        "due_date": (today + timedelta(days=30)).isoformat(),
    })
    assert ac.status_code == 200, ac.text
    active_ctr = ac.json()

    # payment
    pp = admin.post(f"{API}/payments", json={
        "contract_id": active_ctr["id"], "amount": 100, "type": "interest_only",
        "date": today.isoformat(),
    })
    assert pp.status_code == 200, pp.text

    # overdue contract on motorcycle
    yest = (today - timedelta(days=1)).isoformat()
    two = (today - timedelta(days=2)).isoformat()
    oc = admin.post(f"{API}/contracts", json={
        "client_id": cid, "item_id": moto["id"], "item_type": "motorcycle",
        "loan_amount": 1000, "interest_rate": 15,
        "contract_date": two, "due_date": yest,
    })
    assert oc.status_code == 200, oc.text
    overdue_ctr = oc.json()

    # auction from another contract (electronic)
    ec = admin.post(f"{API}/contracts", json={
        "client_id": cid, "item_id": elec["id"], "item_type": "electronic",
        "loan_amount": 500, "interest_rate": 15,
        "contract_date": two, "due_date": yest,
    }).json()
    au = admin.post(f"{API}/auctions/move", json={
        "contract_id": ec["id"], "starting_price": 600,
    })
    assert au.status_code == 200, au.text

    return {"car": car, "moto": moto, "elec": elec,
            "active": active_ctr, "overdue": overdue_ctr, "client_id": cid}


# ---------- location field ----------
class TestLocation:
    def test_car_location_persists(self, admin, seed):
        car = admin.get(f"{API}/items/car/{seed['car']['id']}").json()
        assert car["location"] == "Warehouse A"

    def test_motorcycle_location_persists(self, admin, seed):
        m = admin.get(f"{API}/items/motorcycle/{seed['moto']['id']}").json()
        assert m["location"] == "Shop"

    def test_electronic_location_persists(self, admin, seed):
        e = admin.get(f"{API}/items/electronic/{seed['elec']['id']}").json()
        assert e["location"] == "Safe"


# ---------- /api/reports/v2/* ----------
class TestReportsV2:
    def _g(self, admin, path, **q):
        return admin.get(f"{API}/reports/v2/{path}", params=q)

    def test_active_contracts(self, admin, seed):
        r = self._g(admin, "active-contracts")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["total_contracts", "total_loan", "tax_accumulate", "almost_expired"]:
            assert k in d["kpis"]
            assert isinstance(d["kpis"][k], (int, float))
        assert "columns" in d and "rows" in d
        # every row should have status == active
        for row in d["rows"]:
            assert row["status"] == "active"

    def test_payments(self, admin, seed):
        r = self._g(admin, "payments")
        assert r.status_code == 200
        d = r.json()
        for k in ["total_transactions", "total_payments", "interest_received", "total_penalty"]:
            assert k in d["kpis"]
        # interest_received only counts interest_only payments
        manual_io = sum(
            float(p["amount"]) for p in d["rows"] if p.get("type") == "interest_only"
        )
        assert abs(d["kpis"]["interest_received"] - round(manual_io, 2)) < 0.01

    def test_overdue(self, admin, seed):
        r = self._g(admin, "overdue")
        assert r.status_code == 200
        d = r.json()
        for k in ["total_overdue", "total_outstanding", "total_interest", "near_expired"]:
            assert k in d["kpis"]
        for row in d["rows"]:
            assert row["status"] == "overdue"
        # total_outstanding = sum of principal_remaining
        s = sum(float(row.get("principal_remaining", 0) or 0) for row in d["rows"])
        assert abs(d["kpis"]["total_outstanding"] - round(s, 2)) < 0.01

    def test_auction(self, admin, seed):
        r = self._g(admin, "auction")
        assert r.status_code == 200
        d = r.json()
        for k in ["total_auction", "total_amount"]:
            assert k in d["kpis"]
        assert d["kpis"]["total_auction"] >= 1
        # total_amount uses sold_price else starting_price
        exp = sum(float(row.get("sold_price") or row.get("starting_price") or 0) for row in d["rows"])
        assert abs(d["kpis"]["total_amount"] - round(exp, 2)) < 0.01

    def test_inventory(self, admin, seed):
        r = self._g(admin, "inventory")
        assert r.status_code == 200
        d = r.json()
        for k in ["total_items", "total_amount", "active_items", "overdue_items", "by_type"]:
            assert k in d["kpis"]
        bt = d["kpis"]["by_type"]
        for kk in ["car", "motorcycle", "electronic"]:
            assert kk in bt
        # location column included
        assert "location" in d["columns"]
        # at least one row has our seeded location
        locs = [row.get("location") for row in d["rows"]]
        assert "Warehouse A" in locs

    def test_financial(self, admin, seed):
        r = self._g(admin, "financial")
        assert r.status_code == 200
        d = r.json()
        for k in ["total_loan", "total_payment", "interest_received", "profit", "penalty_paid", "penalty_outstanding"]:
            assert k in d["kpis"]
        # Nov-2026 spec: profit = interest_received + penalty_paid (never adds unpaid penalty)
        assert abs(
            d["kpis"]["profit"] - round(d["kpis"]["interest_received"] + d["kpis"]["penalty_paid"], 2)
        ) < 0.01

    def test_unknown_report_400(self, admin):
        r = admin.get(f"{API}/reports/v2/does-not-exist")
        assert r.status_code == 400

    def test_filter_year_narrows(self, admin, seed):
        r1 = self._g(admin, "active-contracts").json()
        r2 = self._g(admin, "active-contracts", year=2000).json()  # no active contracts in 2000
        assert len(r2["rows"]) == 0
        assert r1["kpis"]["total_contracts"] >= 0

    def test_filter_category_inventory(self, admin, seed):
        r = self._g(admin, "inventory", category="car").json()
        for row in r["rows"]:
            assert row["kind"] == "car"


# ---------- exports ----------
class TestExports:
    def test_financial_xlsx(self, admin, seed):
        r = admin.get(f"{API}/reports/v2/financial/export", params={"format": "xlsx"})
        assert r.status_code == 200, r.text
        ct = r.headers["content-type"]
        assert "openxmlformats-officedocument.spreadsheetml.sheet" in ct
        assert len(r.content) > 4096
        assert r.content[:2] == b"PK"

    def test_active_pdf(self, admin, seed):
        r = admin.get(f"{API}/reports/v2/active-contracts/export", params={"format": "pdf"})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_payments_csv(self, admin, seed):
        r = admin.get(f"{API}/reports/v2/payments/export", params={"format": "csv"})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/csv")
        body = r.content.decode("utf-8")
        # header line should have receipt_number column
        first_line = body.splitlines()[0]
        assert "receipt_number" in first_line
        assert "contract_number" in first_line
