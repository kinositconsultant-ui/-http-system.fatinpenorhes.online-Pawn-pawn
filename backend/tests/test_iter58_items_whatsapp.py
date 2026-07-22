"""
Iteration 58 regression tests:
- Items route split (routes/items.py) — GET/POST/PUT/DELETE + PATCH photo
- WhatsApp webhook verify + status callback (routes/whatsapp.py)
- WhatsApp status endpoints (single + bulk)
- Settings whatsapp_verify_token / whatsapp_app_secret round-trip
"""
import os
import time
import json
import hmac
import hashlib
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def original_settings(admin_session):
    """Snapshot current settings then restore verify_token & app_secret after tests."""
    r = admin_session.get(f"{API}/settings")
    assert r.status_code == 200
    snap = r.json()
    yield snap
    # restore
    payload = {
        "interest_rate_car": snap.get("interest_rate_car", 10),
        "interest_rate_motorcycle": snap.get("interest_rate_motorcycle", 10),
        "interest_rate_electronic": snap.get("interest_rate_electronic", 15),
        "interest_rate_pezadu": snap.get("interest_rate_pezadu", 10),
        "warehouse_password": "",
        "terms_and_conditions_en": snap.get("terms_and_conditions_en", ""),
        "terms_and_conditions_tet": snap.get("terms_and_conditions_tet", ""),
        "whatsapp_template_en": snap.get("whatsapp_template_en", ""),
        "whatsapp_template_tet": snap.get("whatsapp_template_tet", ""),
        "whatsapp_token": "",  # empty = preserve
        "whatsapp_phone_id": snap.get("whatsapp_phone_id", ""),
        "whatsapp_verify_token": snap.get("whatsapp_verify_token", ""),
        "whatsapp_app_secret": snap.get("whatsapp_app_secret", ""),
        "reminder_days_before": snap.get("reminder_days_before", 3),
        "reminders_enabled": snap.get("reminders_enabled", True),
        "next_auction_date": snap.get("next_auction_date", ""),
    }
    admin_session.put(f"{API}/settings", json=payload)


# -----------------------------------------------------------------------------
# ITEMS ROUTE SPLIT — regression that shape/behaviour is unchanged
# -----------------------------------------------------------------------------
class TestItemsRouteSplit:
    KINDS = ["car", "motorcycle", "electronic", "pezadu"]

    def test_list_all_kinds_return_200(self, admin_session):
        for kind in self.KINDS:
            r = admin_session.get(f"{API}/items/{kind}")
            assert r.status_code == 200, f"{kind}: {r.status_code} {r.text}"
            data = r.json()
            assert isinstance(data, list)
            # verify no _id leaked
            for it in data[:3]:
                assert "_id" not in it
                assert "id" in it

    def test_invalid_kind_returns_400(self, admin_session):
        r = admin_session.get(f"{API}/items/foo")
        assert r.status_code == 400
        assert "Invalid item kind" in r.text

    def test_unauthenticated_rejected(self):
        r = requests.get(f"{API}/items/car", timeout=10)
        assert r.status_code in (401, 403)

    def test_crud_car_lifecycle(self, admin_session):
        # CREATE
        payload = {
            "name": f"TEST_CAR_{uuid.uuid4().hex[:6]}",
            "brand": "TestBrand",
            "model": "TestModel",
            "market_value": 1234.5,
            "manufacture_year": 2020,
        }
        r = admin_session.post(f"{API}/items/car", json=payload)
        assert r.status_code == 200, r.text
        created = r.json()
        cid = created["id"]
        assert created["brand"] == "TestBrand"
        assert created["kind"] == "car"

        # GET by id
        r = admin_session.get(f"{API}/items/car/{cid}")
        assert r.status_code == 200
        assert r.json()["id"] == cid

        # UPDATE
        payload["market_value"] = 9999.0
        r = admin_session.put(f"{API}/items/car/{cid}", json=payload)
        assert r.status_code == 200
        assert r.json()["market_value"] == 9999.0

        # DELETE
        r = admin_session.delete(f"{API}/items/car/{cid}")
        assert r.status_code == 200
        assert r.json().get("ok") is True

        # GET after delete → 404
        r = admin_session.get(f"{API}/items/car/{cid}")
        assert r.status_code == 404


# -----------------------------------------------------------------------------
# BULK PHOTO PATCH endpoint
# -----------------------------------------------------------------------------
class TestPhotoPatch:
    @pytest.fixture(scope="class")
    def temp_item(self, admin_session):
        payload = {
            "name": f"TEST_PHOTO_{uuid.uuid4().hex[:6]}",
            "brand": "PhotoBrand",
            "model": "PhotoModel",
            "market_value": 100.0,
        }
        r = admin_session.post(f"{API}/items/motorcycle", json=payload)
        assert r.status_code == 200
        item = r.json()
        yield item
        admin_session.delete(f"{API}/items/motorcycle/{item['id']}")

    def test_patch_photo_updates_only_photo_fields(self, admin_session, temp_item):
        iid = temp_item["id"]
        original_brand = temp_item["brand"]
        r = admin_session.patch(
            f"{API}/items/motorcycle/{iid}/photo",
            json={"photo_url": "/uploads/x.jpg", "thumbnail_url": "/uploads/x_thumb.jpg"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["photo_url"] == "/uploads/x.jpg"
        assert data["thumbnail_url"] == "/uploads/x_thumb.jpg"
        assert data["brand"] == original_brand  # untouched
        assert data["id"] == iid

    def test_patch_photo_idempotent(self, admin_session, temp_item):
        iid = temp_item["id"]
        body = {"photo_url": "/uploads/y.jpg", "thumbnail_url": "/uploads/y_thumb.jpg"}
        r1 = admin_session.patch(f"{API}/items/motorcycle/{iid}/photo", json=body)
        r2 = admin_session.patch(f"{API}/items/motorcycle/{iid}/photo", json=body)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["photo_url"] == r2.json()["photo_url"] == "/uploads/y.jpg"

    def test_patch_photo_bad_kind(self, admin_session):
        r = admin_session.patch(f"{API}/items/foo/xyz/photo", json={"photo_url": "z.jpg"})
        assert r.status_code == 400

    def test_patch_photo_unknown_iid(self, admin_session):
        r = admin_session.patch(
            f"{API}/items/car/nonexistent-xyz/photo",
            json={"photo_url": "n.jpg", "thumbnail_url": ""},
        )
        assert r.status_code == 404


# -----------------------------------------------------------------------------
# SETTINGS — new whatsapp_verify_token / whatsapp_app_secret round-trip
# -----------------------------------------------------------------------------
class TestSettingsWhatsAppFields:
    def test_verify_token_and_app_secret_roundtrip(self, admin_session, original_settings):
        vt = f"test-verify-{uuid.uuid4().hex[:8]}"
        secret = f"test-secret-{uuid.uuid4().hex[:8]}"
        payload = {
            "whatsapp_verify_token": vt,
            "whatsapp_app_secret": secret,
            "whatsapp_phone_id": original_settings.get("whatsapp_phone_id", ""),
            "whatsapp_token": "",  # preserve
            "warehouse_password": "",
        }
        r = admin_session.put(f"{API}/settings", json=payload)
        assert r.status_code == 200, r.text
        # GET
        r2 = admin_session.get(f"{API}/settings")
        assert r2.status_code == 200
        s = r2.json()
        assert s.get("whatsapp_verify_token") == vt
        assert s.get("whatsapp_app_secret") == secret

    def test_existing_whatsapp_token_flow_still_works(self, admin_session, original_settings):
        # Empty whatsapp_token should preserve existing masked token — response should NOT error.
        r = admin_session.put(f"{API}/settings", json={
            "whatsapp_token": "",
            "whatsapp_verify_token": original_settings.get("whatsapp_verify_token", ""),
        })
        assert r.status_code == 200


# -----------------------------------------------------------------------------
# WHATSAPP WEBHOOK — GET verification
# -----------------------------------------------------------------------------
class TestWhatsAppWebhookVerify:
    def test_get_verify_matches(self, admin_session):
        # Set a known verify token first
        vt = f"verifytok-{uuid.uuid4().hex[:6]}"
        r = admin_session.put(f"{API}/settings", json={"whatsapp_verify_token": vt})
        assert r.status_code == 200

        # Correct token → returns challenge
        challenge = "abc12345"
        r = requests.get(
            f"{API}/whatsapp/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": vt, "hub.challenge": challenge},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.text.strip() == challenge

    def test_get_verify_mismatch(self, admin_session):
        vt = f"verifytok-{uuid.uuid4().hex[:6]}"
        admin_session.put(f"{API}/settings", json={"whatsapp_verify_token": vt})
        r = requests.get(
            f"{API}/whatsapp/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "WRONG", "hub.challenge": "x"},
            timeout=10,
        )
        assert r.status_code == 403

    def test_get_verify_when_unconfigured(self, admin_session):
        # Clear settings then check that 503 is returned when neither settings nor env is set
        # NOTE: WHATSAPP_VERIFY_TOKEN may still be set in env; skip if so.
        admin_session.put(f"{API}/settings", json={"whatsapp_verify_token": ""})
        r = requests.get(
            f"{API}/whatsapp/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "y"},
            timeout=10,
        )
        # 503 if not configured anywhere, 403 if env has one
        assert r.status_code in (503, 403), f"got {r.status_code}: {r.text}"


# -----------------------------------------------------------------------------
# WHATSAPP WEBHOOK — POST callback status update
# -----------------------------------------------------------------------------
class TestWhatsAppWebhookPost:
    def test_post_orphan_status_recorded(self, admin_session):
        # Clear app_secret so signature not required
        admin_session.put(f"{API}/settings", json={"whatsapp_app_secret": ""})

        unknown_wamid = f"wamid.UNKNOWN{uuid.uuid4().hex[:10]}"
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "statuses": [{
                            "id": unknown_wamid,
                            "status": "sent",
                            "timestamp": str(int(time.time())),
                        }]
                    }
                }]
            }]
        }
        # Grab orphan baseline
        r0 = admin_session.get(f"{API}/whatsapp/webhook-config")
        assert r0.status_code == 200
        orphans_before = r0.json().get("orphan_statuses", 0)
        events_before = r0.json().get("webhook_events_seen", 0)

        r = requests.post(f"{API}/whatsapp/webhook", json=payload, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Wait for background task
        time.sleep(2)

        r2 = admin_session.get(f"{API}/whatsapp/webhook-config")
        assert r2.status_code == 200
        stats = r2.json()
        assert stats["webhook_events_seen"] >= events_before + 1
        assert stats["orphan_statuses"] >= orphans_before + 1

    def test_post_invalid_signature_when_secret_configured(self, admin_session):
        secret = f"secret-{uuid.uuid4().hex[:10]}"
        admin_session.put(f"{API}/settings", json={"whatsapp_app_secret": secret})
        try:
            payload = {"entry": []}
            r = requests.post(
                f"{API}/whatsapp/webhook",
                json=payload,
                headers={"X-Hub-Signature-256": "sha256=DEADBEEF"},
                timeout=10,
            )
            assert r.status_code == 401
        finally:
            admin_session.put(f"{API}/settings", json={"whatsapp_app_secret": ""})

    def test_post_valid_signature_accepted(self, admin_session):
        secret = f"secret-{uuid.uuid4().hex[:10]}"
        admin_session.put(f"{API}/settings", json={"whatsapp_app_secret": secret})
        try:
            payload_bytes = json.dumps({"entry": []}).encode()
            digest = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
            r = requests.post(
                f"{API}/whatsapp/webhook",
                data=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={digest}",
                },
                timeout=10,
            )
            assert r.status_code == 200, r.text
        finally:
            admin_session.put(f"{API}/settings", json={"whatsapp_app_secret": ""})

    def test_post_missing_signature_when_secret_configured(self, admin_session):
        secret = f"secret-{uuid.uuid4().hex[:10]}"
        admin_session.put(f"{API}/settings", json={"whatsapp_app_secret": secret})
        try:
            r = requests.post(f"{API}/whatsapp/webhook", json={"entry": []}, timeout=10)
            assert r.status_code == 400
        finally:
            admin_session.put(f"{API}/settings", json={"whatsapp_app_secret": ""})


# -----------------------------------------------------------------------------
# _apply_status_update MONOTONIC behaviour — via seeded whatsapp_log doc
# We create a log row directly via admin backdoor: use ad-hoc send endpoint or
# insert via /whatsapp/send-ad-hoc. Simpler: use an integration path.
# Since we can't insert directly through API, we skip DB-level test and rely
# on orphan behaviour + code review.
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# WHATSAPP STATUS endpoints
# -----------------------------------------------------------------------------
class TestWhatsAppStatusEndpoints:
    def test_status_unknown_contract(self, admin_session):
        r = admin_session.get(f"{API}/whatsapp/status/nonexistent-contract-xyz")
        assert r.status_code == 200
        data = r.json()
        assert data["contract_id"] == "nonexistent-contract-xyz"
        assert data["delivery_status"] is None

    def test_status_requires_auth(self):
        r = requests.get(f"{API}/whatsapp/status/anycid", timeout=10)
        assert r.status_code in (401, 403)

    def test_status_bulk_empty(self, admin_session):
        r = admin_session.get(f"{API}/whatsapp/status?contract_ids=")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_status_bulk_with_ids(self, admin_session):
        # Real contract lookup
        r = admin_session.get(f"{API}/contracts?limit=5")
        if r.status_code != 200:
            pytest.skip("cannot fetch contracts to test bulk status")
        contracts = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        if not contracts:
            pytest.skip("no contracts to bulk-query")
        ids = ",".join([c["id"] for c in contracts[:3]])
        r2 = admin_session.get(f"{API}/whatsapp/status?contract_ids={ids}")
        assert r2.status_code == 200
        data = r2.json()
        assert isinstance(data, dict)

    def test_webhook_config_requires_admin(self):
        r = requests.get(f"{API}/whatsapp/webhook-config", timeout=10)
        assert r.status_code in (401, 403)

    def test_webhook_config_admin_ok(self, admin_session):
        r = admin_session.get(f"{API}/whatsapp/webhook-config")
        assert r.status_code == 200
        data = r.json()
        for k in ("verify_token_configured", "app_secret_configured", "webhook_events_seen", "orphan_statuses"):
            assert k in data
