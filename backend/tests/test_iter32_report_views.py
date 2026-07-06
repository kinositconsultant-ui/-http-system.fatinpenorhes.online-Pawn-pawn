"""Iteration 32 — Report Saved Views (per-user tab+filter+sort presets)."""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def api_sess():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
    )
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(autouse=True)
def _cleanup(api_sess):
    yield
    for v in api_sess.get(f"{BASE_URL}/api/report-views").json():
        api_sess.delete(f"{BASE_URL}/api/report-views/{v['id']}")


def test_requires_auth():
    r = requests.get(f"{BASE_URL}/api/report-views")
    assert r.status_code == 401
    r2 = requests.post(f"{BASE_URL}/api/report-views", json={"name": "x", "tab": "y"})
    assert r2.status_code == 401


def test_create_list_delete_view(api_sess):
    name = f"Overdue-{uuid.uuid4().hex[:6]}"
    payload = {
        "name": name,
        "tab": "overdue",
        "filters": {"category": "car", "year": "2026"},
        "sort": {"key": "due_date", "dir": "asc"},
    }
    r = api_sess.post(f"{BASE_URL}/api/report-views", json=payload)
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["id"]
    assert view["name"] == name
    assert view["tab"] == "overdue"
    assert view["filters"] == {"category": "car", "year": "2026"}
    assert view["sort"] == {"key": "due_date", "dir": "asc"}

    listing = api_sess.get(f"{BASE_URL}/api/report-views").json()
    assert any(v["id"] == view["id"] for v in listing)

    r_del = api_sess.delete(f"{BASE_URL}/api/report-views/{view['id']}")
    assert r_del.status_code == 200
    assert r_del.json() == {"ok": True}

    listing2 = api_sess.get(f"{BASE_URL}/api/report-views").json()
    assert not any(v["id"] == view["id"] for v in listing2)


def test_upsert_by_case_insensitive_name(api_sess):
    name = f"MyView-{uuid.uuid4().hex[:6]}"
    r1 = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": name, "tab": "payments", "filters": {"month": "5"},
    })
    id1 = r1.json()["id"]
    # Same name but different case → should UPDATE (same id)
    r2 = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": name.upper(), "tab": "payments", "filters": {"month": "6"},
    })
    assert r2.status_code == 200
    assert r2.json()["id"] == id1
    assert r2.json()["filters"] == {"month": "6"}
    listing = api_sess.get(f"{BASE_URL}/api/report-views").json()
    matching = [v for v in listing if v["id"] == id1]
    assert len(matching) == 1


def test_sort_optional_can_be_null(api_sess):
    r = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": f"NoSort-{uuid.uuid4().hex[:6]}", "tab": "financial", "filters": {},
    })
    assert r.status_code == 200
    assert r.json()["sort"] is None


def test_delete_missing_returns_404(api_sess):
    r = api_sess.delete(f"{BASE_URL}/api/report-views/does-not-exist")
    assert r.status_code == 404


def test_invalid_sort_direction_rejected(api_sess):
    r = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": "bad", "tab": "overdue", "sort": {"key": "x", "dir": "sideways"},
    })
    assert r.status_code == 422


def test_pin_toggle(api_sess):
    r = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": f"Pin-{uuid.uuid4().hex[:6]}", "tab": "overdue", "filters": {},
    })
    view = r.json()
    assert view["pinned"] is False

    r1 = api_sess.patch(f"{BASE_URL}/api/report-views/{view['id']}/pin")
    assert r1.status_code == 200
    assert r1.json()["pinned"] is True

    r2 = api_sess.patch(f"{BASE_URL}/api/report-views/{view['id']}/pin")
    assert r2.status_code == 200
    assert r2.json()["pinned"] is False

    # Non-existent id → 404
    r3 = api_sess.patch(f"{BASE_URL}/api/report-views/nope/pin")
    assert r3.status_code == 404


def test_upsert_preserves_pinned_state(api_sess):
    name = f"Persist-{uuid.uuid4().hex[:6]}"
    r = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": name, "tab": "overdue", "filters": {},
    })
    vid = r.json()["id"]
    api_sess.patch(f"{BASE_URL}/api/report-views/{vid}/pin")  # pin it
    # Now re-upsert with new filters but no pinned flag
    r2 = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": name, "tab": "overdue", "filters": {"category": "car"},
    })
    assert r2.status_code == 200
    assert r2.json()["id"] == vid
    assert r2.json()["pinned"] is True  # preserved


def test_alert_threshold_set_and_clear(api_sess):
    r = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": f"Thr-{uuid.uuid4().hex[:6]}", "tab": "overdue",
    })
    vid = r.json()["id"]
    assert r.json().get("alert_threshold") is None

    # set threshold
    r1 = api_sess.patch(
        f"{BASE_URL}/api/report-views/{vid}/threshold",
        json={"alert_threshold": 25},
    )
    assert r1.status_code == 200
    assert r1.json()["alert_threshold"] == 25

    # clear via null
    r2 = api_sess.patch(
        f"{BASE_URL}/api/report-views/{vid}/threshold",
        json={"alert_threshold": None},
    )
    assert r2.status_code == 200
    assert r2.json()["alert_threshold"] is None

    # invalid (negative)
    r3 = api_sess.patch(
        f"{BASE_URL}/api/report-views/{vid}/threshold",
        json={"alert_threshold": -5},
    )
    assert r3.status_code == 422

    # 404 on missing
    r4 = api_sess.patch(
        f"{BASE_URL}/api/report-views/nope/threshold",
        json={"alert_threshold": 10},
    )
    assert r4.status_code == 404


def test_upsert_preserves_threshold(api_sess):
    name = f"KeepThr-{uuid.uuid4().hex[:6]}"
    r = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": name, "tab": "overdue", "alert_threshold": 40,
    })
    vid = r.json()["id"]
    assert r.json()["alert_threshold"] == 40
    # Upsert without alert_threshold field → should keep 40
    r2 = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": name, "tab": "overdue", "filters": {"category": "car"},
    })
    assert r2.json()["id"] == vid
    assert r2.json()["alert_threshold"] == 40
