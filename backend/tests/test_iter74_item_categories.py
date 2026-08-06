"""Iter 74 — Car & Motorcycle category field.

Verifies:
- POST /api/items/car with each of the 8 car categories succeeds and persists.
- POST /api/items/motorcycle with each of 7 motorcycle categories succeeds and persists.
- Backward compat: POST without category defaults to empty string.
- GET /api/items/{kind} includes `category` on all rows (empty for legacy).
"""
from __future__ import annotations

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pawnly-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CAR_CATS = ["sedan", "suv", "pickup", "truck", "van", "hatchback", "mini_bus", "other"]
MOTO_CATS = ["scooter", "cub", "sport", "adventure", "dirt_bike", "e_bike", "other"]


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": "admin@fatinpenhores.tl", "password": "admin123"},
               timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def _create(session, kind, payload):
    r = session.post(f"{API}/items/{kind}", json=payload, timeout=15)
    return r


def _delete(session, kind, iid):
    session.delete(f"{API}/items/{kind}/{iid}", timeout=15)


class TestCarCategories:
    def test_all_car_categories_accepted(self, admin_session):
        created = []
        try:
            for cat in CAR_CATS:
                payload = {"brand": "TEST_Toyota", "model": f"TEST_{cat}", "category": cat}
                r = _create(admin_session, "car", payload)
                assert r.status_code == 200, f"cat={cat}: {r.status_code} {r.text}"
                body = r.json()
                assert body.get("category") == cat, f"expected category={cat}, got {body.get('category')}"
                assert "id" in body
                created.append(body["id"])

                # GET verify persisted
                g = admin_session.get(f"{API}/items/car/{body['id']}", timeout=15)
                assert g.status_code == 200
                assert g.json().get("category") == cat
        finally:
            for iid in created:
                _delete(admin_session, "car", iid)

    def test_car_without_category_defaults_empty(self, admin_session):
        payload = {"brand": "TEST_Honda", "model": "TEST_NoCat"}
        r = _create(admin_session, "car", payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("category") == "", f"expected empty, got {body.get('category')!r}"
        _delete(admin_session, "car", body["id"])

    def test_get_car_list_has_category_field(self, admin_session):
        # Create one with category, one without
        r1 = _create(admin_session, "car", {"brand": "TEST_A", "model": "TEST_A", "category": "suv"})
        r2 = _create(admin_session, "car", {"brand": "TEST_B", "model": "TEST_B"})
        assert r1.status_code == 200 and r2.status_code == 200
        try:
            r = admin_session.get(f"{API}/items/car", timeout=15)
            assert r.status_code == 200
            rows = r.json()
            for row in rows:
                assert "category" in row, f"row missing category: {row.get('id')}"
        finally:
            _delete(admin_session, "car", r1.json()["id"])
            _delete(admin_session, "car", r2.json()["id"])


class TestMotorcycleCategories:
    def test_all_motorcycle_categories_accepted(self, admin_session):
        created = []
        try:
            for cat in MOTO_CATS:
                payload = {"brand": "TEST_Yamaha", "model": f"TEST_{cat}", "category": cat}
                r = _create(admin_session, "motorcycle", payload)
                assert r.status_code == 200, f"cat={cat}: {r.status_code} {r.text}"
                body = r.json()
                assert body.get("category") == cat
                created.append(body["id"])

                g = admin_session.get(f"{API}/items/motorcycle/{body['id']}", timeout=15)
                assert g.status_code == 200
                assert g.json().get("category") == cat
        finally:
            for iid in created:
                _delete(admin_session, "motorcycle", iid)

    def test_motorcycle_without_category_defaults_empty(self, admin_session):
        payload = {"brand": "TEST_Suzuki", "model": "TEST_NoCat"}
        r = _create(admin_session, "motorcycle", payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("category") == ""
        _delete(admin_session, "motorcycle", body["id"])
