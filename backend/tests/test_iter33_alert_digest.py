"""Iteration 33 — Pinned View Alert Digest."""
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


@pytest.fixture
def pinned_view(api_sess):
    r = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": f"Alert-{uuid.uuid4().hex[:6]}",
        "tab": "overdue",
        "pinned": True,
        "alert_threshold": 5,
    })
    assert r.status_code == 200, r.text
    v = r.json()
    yield v
    api_sess.delete(f"{BASE_URL}/api/report-views/{v['id']}")


def test_preview_requires_auth():
    r = requests.get(f"{BASE_URL}/api/alerts/preview")
    assert r.status_code == 401


def test_preview_returns_breaches(api_sess, pinned_view):
    r = api_sess.get(f"{BASE_URL}/api/alerts/preview")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"]
    assert body["email"] == ADMIN_EMAIL
    breaches = body["breaches"]
    ours = [b for b in breaches if b["view_id"] == pinned_view["id"]]
    assert len(ours) == 1
    b = ours[0]
    assert b["threshold"] == 5
    assert b["count"] > 5   # 72 overdue rows in seed data
    assert b["over_by"] == b["count"] - 5


def test_no_breach_when_threshold_above_count(api_sess):
    r = api_sess.post(f"{BASE_URL}/api/report-views", json={
        "name": f"AlertHi-{uuid.uuid4().hex[:6]}",
        "tab": "overdue",
        "pinned": True,
        "alert_threshold": 100000,  # above any real count
    })
    vid = r.json()["id"]
    try:
        body = api_sess.get(f"{BASE_URL}/api/alerts/preview").json()
        assert not any(b["view_id"] == vid for b in body["breaches"])
    finally:
        api_sess.delete(f"{BASE_URL}/api/report-views/{vid}")


def test_run_now_admin_only(api_sess, pinned_view):
    r = api_sess.post(f"{BASE_URL}/api/alerts/run-now")
    assert r.status_code == 200
    body = r.json()
    assert body["users_scanned"] > 0
    # We have a pinned view with a breach → at least one email attempted
    assert body["emails_sent"] + body["emails_mocked"] >= 1
    assert "next_alert_digest_run_at" not in body  # this endpoint doesn't expose scheduler
    assert body["email_configured"] is False       # Resend not configured in preview env
    # unauth
    r2 = requests.post(f"{BASE_URL}/api/alerts/run-now")
    assert r2.status_code == 401


def test_history_records_only_breaches(api_sess, pinned_view):
    # Trigger a run to persist a digest
    api_sess.post(f"{BASE_URL}/api/alerts/run-now")
    r = api_sess.get(f"{BASE_URL}/api/alerts/history")
    assert r.status_code == 200
    hist = r.json()
    assert isinstance(hist, list)
    assert len(hist) >= 1
    latest = hist[0]
    assert latest["user_id"]
    assert latest["breaches"], "digest history should contain breach details"


def test_scheduler_exposes_next_alert_run(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/admin/backups/schedule")
    assert r.status_code == 200
    data = r.json()
    assert "next_alert_digest_run_at" in data
    assert data["next_alert_digest_run_at"] is not None
