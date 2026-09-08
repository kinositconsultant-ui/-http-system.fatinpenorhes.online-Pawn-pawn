"""Iteration 82: Pickup Reminder Toggle + Overdue Pickup Nudge tests.

Covers:
- GET /api/settings returns pickup_notify_enabled, pickup_message_tet/en
- PUT /api/settings persists pickup_notify_enabled and messages
- Payment full-pay -> pickup_notification 'disabled' when toggle off, 'mocked' when on
- Custom English pickup message: rendered body includes placeholders replaced (in whatsapp/logs)
- GET /api/warehouse/releases/pending includes days_waiting, last_nudge_at
- GET /api/warehouse/releases/overdue?days=7 returns only >=7-day entries incl. seeded CTR-2026-0899
- POST /api/warehouse/releases/{cid}/nudge -> mocked; audit + whatsapp logs updated
- Nudge on non-redeemed -> 400
- Unauthenticated nudge -> 401
"""
from __future__ import annotations
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"

SEEDED_OVERDUE_CID = None
try:
    with open("/tmp/cid3") as f:
        SEEDED_OVERDUE_CID = f.read().strip() or None
except FileNotFoundError:
    pass


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def _clean_settings_body(s: dict) -> dict:
    for k in ("whatsapp_token_masked", "whatsapp_connected", "warehouse_locked", "id", "_id"):
        s.pop(k, None)
    return s


@pytest.fixture(scope="module")
def initial_settings(admin):
    r = admin.get(f"{BASE_URL}/api/settings", timeout=30)
    assert r.status_code == 200
    return r.json()


# --- Settings shape ---
class TestSettingsShape:
    def test_settings_has_pickup_fields(self, initial_settings):
        assert "pickup_notify_enabled" in initial_settings
        assert isinstance(initial_settings["pickup_notify_enabled"], bool)
        assert "pickup_message_tet" in initial_settings
        assert "pickup_message_en" in initial_settings
        assert isinstance(initial_settings["pickup_message_tet"], str)
        assert isinstance(initial_settings["pickup_message_en"], str)


# --- Persistence + payment behavior ---
class TestPickupToggleAndPayment:
    @pytest.fixture(scope="class")
    def client_id(self, admin):
        # seeded per the request note
        cid = "75b43fa2-75d4-4cb5-a1a6-976264cb45bf"
        r = admin.get(f"{BASE_URL}/api/clients/{cid}", timeout=30)
        if r.status_code != 200:
            r2 = admin.get(f"{BASE_URL}/api/clients", timeout=30)
            data = r2.json()
            items = data if isinstance(data, list) else data.get("items") or data.get("results") or []
            assert items
            return items[0]["id"]
        return cid

    @pytest.fixture(scope="class")
    def new_contract(self, admin, client_id):
        # Create an active contract of type 'other' (fungible) to avoid running out of stock cars
        r = admin.get(f"{BASE_URL}/api/items", timeout=30)
        # Use car type - most reliable existing type
        cars = admin.get(f"{BASE_URL}/api/items/car", timeout=30).json()
        items = cars if isinstance(cars, list) else cars.get("items") or []
        in_stock = next((i for i in items if i.get("status") == "in_stock"), None)
        if not in_stock:
            pytest.skip("no in_stock car available for pickup toggle test")
        payload = {
            "client_id": client_id,
            "item_type": "car",
            "item_id": in_stock["id"],
            "loan_amount": 1000,
            "interest_rate": 10,
            "contract_date": "2026-09-01",
            "due_date": "2026-10-01",
        }
        r = admin.post(f"{BASE_URL}/api/contracts", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        cid = r.json()["id"]
        yield cid
        admin.delete(f"{BASE_URL}/api/contracts/{cid}", timeout=30)

    def test_toggle_off_persists_and_disabled_notification(self, admin, initial_settings, new_contract):
        body = _clean_settings_body(dict(initial_settings))
        body["pickup_notify_enabled"] = False
        r = admin.put(f"{BASE_URL}/api/settings", json=body, timeout=30)
        assert r.status_code == 200, r.text
        # verify persisted
        got = admin.get(f"{BASE_URL}/api/settings", timeout=30).json()
        assert got["pickup_notify_enabled"] is False

        # Full pay -> pickup_notification should be 'disabled'
        pay = admin.post(
            f"{BASE_URL}/api/payments",
            json={"contract_id": new_contract, "amount": 1100, "type": "full", "date": "2026-09-05"},
            timeout=30,
        )
        assert pay.status_code in (200, 201), pay.text
        p = pay.json()
        pn = p.get("pickup_notification")
        assert pn is not None, f"no pickup_notification field: {list(p.keys())}"
        assert pn.get("status") == "disabled", f"expected disabled, got {pn}"

    def test_toggle_on_custom_message_renders_placeholders(self, admin, client_id):
        # Now enable + set custom EN message with placeholders; create a NEW contract, full-pay it
        s = admin.get(f"{BASE_URL}/api/settings", timeout=30).json()
        body = _clean_settings_body(dict(s))
        body["pickup_notify_enabled"] = True
        body["pickup_message_en"] = "Hi {name}, contract {contract} paid. Your {item} is ready."
        r = admin.put(f"{BASE_URL}/api/settings", json=body, timeout=30)
        assert r.status_code == 200, r.text

        cars = admin.get(f"{BASE_URL}/api/items/car", timeout=30).json()
        items = cars if isinstance(cars, list) else cars.get("items") or []
        in_stock = next((i for i in items if i.get("status") == "in_stock"), None)
        if not in_stock:
            pytest.skip("no in_stock car available for second toggle test")

        payload = {
            "client_id": client_id,
            "item_type": "car",
            "item_id": in_stock["id"],
            "loan_amount": 1000,
            "interest_rate": 10,
            "contract_date": "2026-09-01",
            "due_date": "2026-10-01",
        }
        c = admin.post(f"{BASE_URL}/api/contracts", json=payload, timeout=30)
        assert c.status_code in (200, 201), c.text
        cid = c.json()["id"]
        try:
            pay = admin.post(
                f"{BASE_URL}/api/payments",
                json={"contract_id": cid, "amount": 1100, "type": "full", "date": "2026-09-05"},
                timeout=30,
            )
            assert pay.status_code in (200, 201), pay.text
            p = pay.json()
            pn = p.get("pickup_notification") or {}
            assert pn.get("status") == "mocked", f"expected mocked got {pn}"
            assert pn.get("to"), "pickup_notification.to phone missing"

            # Verify whatsapp log has rendered body
            time.sleep(1)
            logs = admin.get(f"{BASE_URL}/api/whatsapp/logs", timeout=30).json()
            rows = logs if isinstance(logs, list) else logs.get("items") or logs.get("results") or []
            pickup_logs = [x for x in rows if x.get("template") == "pickup_ready"]
            assert pickup_logs, "no pickup_ready whatsapp log entry"
            # Find one for our contract
            body_text = None
            contract_number = c.json().get("contract_number") or ""
            for lg in pickup_logs:
                b = lg.get("body") or lg.get("message") or ""
                if contract_number and contract_number in b:
                    body_text = b
                    break
            if body_text is None:
                body_text = pickup_logs[0].get("body") or pickup_logs[0].get("message") or ""
            assert "{name}" not in body_text and "{contract}" not in body_text and "{item}" not in body_text, \
                f"placeholders not rendered: {body_text}"
            assert "Hi " in body_text and "paid" in body_text and "ready" in body_text.lower(), \
                f"custom EN message not used: {body_text}"
        finally:
            admin.delete(f"{BASE_URL}/api/contracts/{cid}", timeout=30)


# --- Overdue ---
class TestOverdue:
    def test_pending_has_days_waiting_and_last_nudge_at(self, admin):
        r = admin.get(f"{BASE_URL}/api/warehouse/releases/pending", timeout=30)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        if not rows:
            pytest.skip("no pending rows to check")
        row = rows[0]
        assert "days_waiting" in row, f"missing days_waiting: {list(row.keys())}"
        assert isinstance(row["days_waiting"], int)
        assert "last_nudge_at" in row

    def test_overdue_endpoint_only_returns_7plus(self, admin):
        r = admin.get(f"{BASE_URL}/api/warehouse/releases/overdue?days=7", timeout=30)
        assert r.status_code == 200
        rows = r.json()
        for row in rows:
            assert row.get("days_waiting", 0) >= 7, f"non-overdue leaked: {row}"

    def test_seeded_overdue_contract_present(self, admin):
        if not SEEDED_OVERDUE_CID:
            pytest.skip("no /tmp/cid3 seeded cid")
        r = admin.get(f"{BASE_URL}/api/warehouse/releases/overdue?days=7", timeout=30)
        rows = r.json()
        row = next((x for x in rows if x["id"] == SEEDED_OVERDUE_CID), None)
        assert row is not None, f"seeded overdue cid {SEEDED_OVERDUE_CID} not present"
        assert row.get("days_waiting", 0) >= 7

    def test_nudge_mocked_and_updates(self, admin):
        if not SEEDED_OVERDUE_CID:
            pytest.skip("no seeded cid")
        r = admin.post(f"{BASE_URL}/api/warehouse/releases/{SEEDED_OVERDUE_CID}/nudge", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "mocked"
        assert data.get("to")
        assert data.get("nudged_at")

        # last_nudge_at set on pending row
        p = admin.get(f"{BASE_URL}/api/warehouse/releases/pending", timeout=30).json()
        row = next((x for x in p if x["id"] == SEEDED_OVERDUE_CID), None)
        assert row is not None
        assert row.get("last_nudge_at"), "last_nudge_at not set after nudge"

        # whatsapp log with template pickup_nudge
        logs = admin.get(f"{BASE_URL}/api/whatsapp/logs", timeout=30).json()
        rows = logs if isinstance(logs, list) else logs.get("items") or []
        assert any(x.get("template") == "pickup_nudge" for x in rows), "no pickup_nudge log"

        # audit log has action 'whatsapp_pickup_nudge'
        alog = admin.get(f"{BASE_URL}/api/audit-logs", timeout=30)
        if alog.status_code == 200:
            arows = alog.json()
            arows = arows if isinstance(arows, list) else arows.get("items") or []
            assert any(x.get("action") == "whatsapp_pickup_nudge" for x in arows), "no audit entry"

    def test_nudge_non_redeemed_returns_400(self, admin):
        # Find an active (non-redeemed) contract
        r = admin.get(f"{BASE_URL}/api/contracts?status=active", timeout=30)
        assert r.status_code == 200
        d = r.json()
        rows = d if isinstance(d, list) else d.get("items") or d.get("results") or []
        active = next((c for c in rows if c.get("status") == "active"), None)
        if not active:
            pytest.skip("no active contract available")
        r = admin.post(f"{BASE_URL}/api/warehouse/releases/{active['id']}/nudge", timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text}"

    def test_nudge_unauthenticated_401(self):
        if not SEEDED_OVERDUE_CID:
            pytest.skip("no seeded cid")
        r = requests.post(f"{BASE_URL}/api/warehouse/releases/{SEEDED_OVERDUE_CID}/nudge", timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


# --- Cleanup: restore defaults ---
class TestRestoreSettings:
    def test_restore(self, admin):
        s = admin.get(f"{BASE_URL}/api/settings", timeout=30).json()
        body = _clean_settings_body(dict(s))
        body["pickup_notify_enabled"] = True
        body["pickup_message_tet"] = ""
        body["pickup_message_en"] = ""
        r = admin.put(f"{BASE_URL}/api/settings", json=body, timeout=30)
        assert r.status_code == 200
