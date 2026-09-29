"""Iteration 81: Warehouse Release (outbound hand-over) flow tests.

Covers:
- Full-payment redemption -> item status 'redeemed' + contract has redeemed_at
- /api/warehouse/releases/pending listing & orphan filtering
- POST release: happy path, 409 double-release, 400 non-redeemed, 422 empty name, 401 unauth
- Item goes to 'released', active_contract_id unset, /warehouse/releases lists it
- PDF gate-pass endpoint
- Inventory analytics by_status has 'released'
- Released item can be pawned again
- Payment delete reverts item redeemed -> pawned
- Cleanup: delete test contracts
"""
from __future__ import annotations
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def client_id(admin):
    r = admin.get(f"{BASE_URL}/api/clients", timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("results") or []
    assert items, "need a client"
    return items[0]["id"]


@pytest.fixture(scope="module")
def in_stock_car(admin):
    r = admin.get(f"{BASE_URL}/api/items/car", timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("results") or []
    for it in items:
        if it.get("status") == "in_stock":
            return it
    pytest.skip("no in_stock car available")


@pytest.fixture(scope="module")
def context(admin, client_id, in_stock_car):
    """Create first contract, redeem it fully -> hand back state to tests."""
    payload = {
        "client_id": client_id,
        "item_type": "car",
        "item_id": in_stock_car["id"],
        "loan_amount": 1000,
        "interest_rate": 10,
        "contract_date": "2026-06-01",
        "due_date": "2026-07-01",
    }
    r = admin.post(f"{BASE_URL}/api/contracts", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create contract: {r.status_code} {r.text}"
    contract = r.json()
    cid = contract["id"]

    pay = admin.post(
        f"{BASE_URL}/api/payments",
        json={"contract_id": cid, "amount": 1300, "type": "full", "date": "2026-06-05"},
        timeout=30,
    )
    assert pay.status_code in (200, 201), f"payment: {pay.status_code} {pay.text}"
    pay_data = pay.json()
    ctx = {"cid": cid, "item_id": in_stock_car["id"], "payment_response": pay_data, "client_id": client_id}
    yield ctx
    # Cleanup - best-effort
    admin.delete(f"{BASE_URL}/api/contracts/{cid}", timeout=30)


class TestRedemption:
    def test_payment_response_contract_redeemed(self, context):
        p = context["payment_response"]
        contract = p.get("contract") or {}
        assert contract.get("status") == "redeemed", f"expected redeemed, got {contract.get('status')}: keys={list(p.keys())}"

    def test_item_status_redeemed(self, admin, context):
        r = admin.get(f"{BASE_URL}/api/items/car/{context['item_id']}", timeout=30)
        assert r.status_code == 200
        assert r.json().get("status") == "redeemed"

    def test_contract_has_redeemed_at_not_released(self, admin, context):
        r = admin.get(f"{BASE_URL}/api/contracts/{context['cid']}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("redeemed_at")
        assert not d.get("item_released")


class TestPendingQueue:
    def test_pending_contains_contract(self, admin, context):
        r = admin.get(f"{BASE_URL}/api/warehouse/releases/pending", timeout=30)
        assert r.status_code == 200
        rows = r.json()
        row = next((x for x in rows if x["id"] == context["cid"]), None)
        assert row is not None, "contract missing from pending"
        assert row.get("contract_number")
        assert row.get("client_name")
        assert row.get("item")
        assert row.get("group") == "warehouse"
        assert row.get("redeemed_at")

    def test_pending_no_orphans(self, admin):
        r = admin.get(f"{BASE_URL}/api/warehouse/releases/pending", timeout=30)
        assert r.status_code == 200
        for row in r.json():
            # Orphans without an item document must not appear
            assert row.get("item") and row["item"] != {}


class TestReleaseFlow:
    def test_release_validation_empty_name(self, admin, context):
        r = admin.post(
            f"{BASE_URL}/api/warehouse/releases/{context['cid']}",
            json={"collector_name": "   "},
            timeout=30,
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_release_unauthenticated(self, context):
        r = requests.post(
            f"{BASE_URL}/api/warehouse/releases/{context['cid']}",
            json={"collector_name": "Anon"},
            timeout=30,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}"

    def test_release_happy_path(self, admin, context):
        payload = {
            "collector_name": "Maria Soares",
            "collector_id_number": "TL-1",
            "collector_relation": "owner",
            "condition": "good",
            "fuel_percent": 40,
            "mileage_km": 1000,
            "notes": "x",
        }
        r = admin.post(f"{BASE_URL}/api/warehouse/releases/{context['cid']}", json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        d = r.json()
        assert d.get("item_released") is True
        assert d.get("release_collector_name") == "Maria Soares"
        assert d.get("released_by_name")

    def test_release_double_returns_409(self, admin, context):
        r = admin.post(
            f"{BASE_URL}/api/warehouse/releases/{context['cid']}",
            json={"collector_name": "X"},
            timeout=30,
        )
        assert r.status_code == 409

    def test_item_status_released_and_no_active_contract(self, admin, context):
        r = admin.get(f"{BASE_URL}/api/items/car/{context['item_id']}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("status") == "released"
        assert "active_contract_id" not in d or not d.get("active_contract_id")

    def test_releases_history_lists_it(self, admin, context):
        r = admin.get(f"{BASE_URL}/api/warehouse/releases", timeout=30)
        assert r.status_code == 200
        assert any(x["id"] == context["cid"] for x in r.json())

    def test_release_pdf(self, admin, context):
        r = admin.get(f"{BASE_URL}/api/warehouse/releases/{context['cid']}/pdf", timeout=30)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"

    def test_inventory_analytics_has_released(self, admin):
        r = admin.get(f"{BASE_URL}/api/inventory/analytics", timeout=30)
        assert r.status_code == 200
        by_status = r.json().get("by_status") or {}
        assert by_status.get("released", 0) >= 1, f"by_status={by_status}"

    def test_release_on_non_redeemed_contract_returns_400(self, admin, client_id, context):
        # Use a currently 'released' item's contract? No - grab an in_stock car, create fresh contract w/o payment
        r = admin.get(f"{BASE_URL}/api/items/car", timeout=30)
        cars = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        car = next((c for c in cars if c.get("status") == "in_stock" and c["id"] != context["item_id"]), None)
        if not car:
            pytest.skip("no second in_stock car")
        r = admin.post(f"{BASE_URL}/api/contracts", json={
            "client_id": client_id, "item_type": "car", "item_id": car["id"],
            "loan_amount": 100, "interest_rate": 10,
            "contract_date": "2026-06-01", "due_date": "2026-07-01",
        }, timeout=30)
        assert r.status_code in (200, 201)
        cid2 = r.json()["id"]
        try:
            r = admin.post(f"{BASE_URL}/api/warehouse/releases/{cid2}",
                           json={"collector_name": "X"}, timeout=30)
            assert r.status_code == 400
        finally:
            admin.delete(f"{BASE_URL}/api/contracts/{cid2}", timeout=30)


class TestRePawnAndRevert:
    def test_released_item_can_be_pawned_again(self, admin, context, client_id):
        r = admin.post(f"{BASE_URL}/api/contracts", json={
            "client_id": client_id,
            "item_type": "car",
            "item_id": context["item_id"],
            "loan_amount": 500,
            "interest_rate": 10,
            "contract_date": "2026-06-01",
            "due_date": "2026-07-01",
        }, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        context["cid2"] = r.json()["id"]

    def test_payment_delete_reverts_item_to_pawned(self, admin, context):
        cid2 = context.get("cid2")
        if not cid2:
            pytest.skip("no cid2")
        pay = admin.post(f"{BASE_URL}/api/payments", json={
            "contract_id": cid2, "amount": 650, "type": "full", "date": "2026-06-05",
        }, timeout=30)
        assert pay.status_code in (200, 201), f"{pay.status_code} {pay.text}"
        # After redeem, item should be redeemed
        r = admin.get(f"{BASE_URL}/api/items/car/{context['item_id']}", timeout=30)
        assert r.json().get("status") == "redeemed"
        # Find payment id
        pdata = pay.json()
        pid = (pdata.get("payment") or {}).get("id") or pdata.get("id")
        if not pid:
            plist = admin.get(f"{BASE_URL}/api/payments?contract_id={cid2}", timeout=30).json()
            plist = plist if isinstance(plist, list) else plist.get("items", [])
            if plist:
                pid = plist[0].get("id")
        assert pid, f"couldn't find payment id in {pdata}"
        d = admin.delete(f"{BASE_URL}/api/payments/{pid}", timeout=30)
        assert d.status_code in (200, 204), f"{d.status_code} {d.text}"

        r = admin.get(f"{BASE_URL}/api/items/car/{context['item_id']}", timeout=30)
        assert r.json().get("status") == "pawned"
        c = admin.get(f"{BASE_URL}/api/contracts/{cid2}", timeout=30).json()
        assert c.get("status") != "redeemed"
        assert not c.get("redeemed_at")
        # cleanup
        admin.delete(f"{BASE_URL}/api/contracts/{cid2}", timeout=30)
