"""Backend tests for iteration 48 batch:
1. Settings defaults: interest_rate_motorcycle=10 (changed from 15)
2. Existing motorcycle contracts keep their historic stored interest_rate
3. GET /api/auctions enrichment for orphan/unlinked auctions
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://pawnly-pro.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


class TestSettingsDefaults:
    """Article 4 rule change: motorcycle rate 15% → 10%."""

    def test_settings_motorcycle_now_10(self, admin_session):
        r = admin_session.get(f"{API}/settings")
        assert r.status_code == 200
        s = r.json()
        assert s.get("interest_rate_car") == 10, f"car rate wrong: {s.get('interest_rate_car')}"
        assert s.get("interest_rate_motorcycle") == 10, f"motorcycle rate wrong: {s.get('interest_rate_motorcycle')}"
        assert s.get("interest_rate_electronic") == 15
        assert s.get("interest_rate_pezadu") == 10

    def test_existing_motorcycle_contracts_preserve_rate(self, admin_session):
        """Existing motorcycle contracts must keep whatever interest_rate they were created with."""
        r = admin_session.get(f"{API}/contracts")
        assert r.status_code == 200
        moto = [c for c in r.json() if c.get("item_type") == "motorcycle"]
        # not asserting a specific count — just verifying we don't blindly overwrite
        # the historic values on the fly. At least one legacy 15% record must survive.
        if len(moto) > 0:
            legacy_15 = [c for c in moto if c.get("interest_rate") == 15]
            assert len(legacy_15) > 0, "Expected some historic motorcycle contracts at 15% to be preserved"


class TestAuctionOrphanEnrichment:
    """Orphan auction rows now show 'Deleted Contract · CTR-...' or
    'Unlinked · CTR-...' in client_name instead of empty string."""

    def test_auctions_have_no_empty_client_name(self, admin_session):
        r = admin_session.get(f"{API}/auctions")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        empty = [a for a in data if not a.get("client_name")]
        assert len(empty) == 0, f"Found {len(empty)} auctions with empty client_name"

    def test_orphan_auctions_use_deleted_label(self, admin_session):
        r = admin_session.get(f"{API}/auctions")
        assert r.status_code == 200
        data = r.json()
        deleted = [a for a in data if str(a.get("client_name", "")).startswith("Deleted Contract · CTR-")]
        unlinked = [a for a in data if str(a.get("client_name", "")).startswith("Unlinked · CTR-")]
        # At least one orphan label expected in the fixture DB — the review request states
        # "several" orphan rows exist and should use the new labels.
        assert (len(deleted) + len(unlinked)) > 0, "Expected at least one orphan auction with 'Deleted Contract' or 'Unlinked' label"

    def test_deleted_label_matches_contract_number(self, admin_session):
        r = admin_session.get(f"{API}/auctions")
        assert r.status_code == 200
        data = r.json()
        for a in data:
            name = a.get("client_name", "")
            if name.startswith("Deleted Contract · ") or name.startswith("Unlinked · "):
                # The suffix after '· ' should match this auction's contract_number
                suffix = name.split("· ", 1)[1]
                assert suffix == a.get("contract_number"), f"label suffix {suffix!r} != contract_number {a.get('contract_number')!r}"
