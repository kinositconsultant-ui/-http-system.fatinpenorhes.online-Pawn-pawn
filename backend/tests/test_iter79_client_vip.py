"""iter79 — Client VIP tags + Business Dashboard VIP-first sort.

Verifies:
 * PATCH /api/clients/{cid}/tier accepts "vip" and "" (unset)
 * Invalid tier value returns 422
 * Endpoint rejects unauthenticated calls
 * Business Dashboard `expiring_*` lists surface `is_vip` and sort VIPs first
"""
from __future__ import annotations

import os

import pytest
import requests

BASE = os.environ.get(
    "TEST_BASE_URL",
    "https://pawnly-pro.preview.emergentagent.com",
).rstrip("/")


@pytest.fixture(scope="module")
def token() -> str:
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": "admin@fatinpenhores.tl", "password": "admin123"},
        timeout=10,
    )
    r.raise_for_status()
    tok = r.cookies.get("access_token")
    assert tok
    return tok


def H(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _first_client_id(t: str) -> str:
    r = requests.get(f"{BASE}/api/clients", headers=H(t), timeout=15)
    assert r.status_code == 200
    rows = r.json()
    assert rows, "no clients in fixture DB"
    return rows[0]["id"]


def test_tier_requires_auth():
    r = requests.patch(
        f"{BASE}/api/clients/anything/tier", json={"tier": "vip"}, timeout=10
    )
    assert r.status_code in (401, 403)


def test_set_and_unset_vip(token: str):
    cid = _first_client_id(token)
    try:
        r = requests.patch(
            f"{BASE}/api/clients/{cid}/tier",
            json={"tier": "vip"},
            headers=H(token),
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("tier") == "vip"

        r = requests.patch(
            f"{BASE}/api/clients/{cid}/tier",
            json={"tier": ""},
            headers=H(token),
            timeout=10,
        )
        assert r.status_code == 200
        assert (r.json().get("tier") or "") == ""
    finally:
        # Best-effort cleanup — leave tier empty
        requests.patch(
            f"{BASE}/api/clients/{cid}/tier",
            json={"tier": ""},
            headers=H(token),
            timeout=10,
        )


def test_invalid_tier_rejected(token: str):
    cid = _first_client_id(token)
    r = requests.patch(
        f"{BASE}/api/clients/{cid}/tier",
        json={"tier": "gold"},
        headers=H(token),
        timeout=10,
    )
    assert r.status_code == 422


def test_business_dashboard_vip_sort(token: str):
    """VIP-flagged clients should appear first in any expiring list where they
    have a due contract. If no VIP has an expiring contract, the endpoint
    still exposes the `is_vip` field on every row (may be all False)."""
    cid = _first_client_id(token)
    try:
        # Flag first client as VIP
        r = requests.patch(
            f"{BASE}/api/clients/{cid}/tier",
            json={"tier": "vip"},
            headers=H(token),
            timeout=10,
        )
        assert r.status_code == 200

        r = requests.get(f"{BASE}/api/business/dashboard", headers=H(token), timeout=20)
        assert r.status_code == 200
        body = r.json()
        for bucket in ("expiring_7", "expiring_15", "expiring_month2"):
            rows = body.get(bucket) or []
            for row in rows:
                assert "is_vip" in row, f"{bucket} row missing is_vip"
            # If a row's client is our VIP, it must be at position 0 (or all
            # earlier rows must also be VIP)
            for idx, row in enumerate(rows):
                if row.get("is_vip"):
                    # Every row at a lower index must also be VIP
                    assert all(rows[j].get("is_vip") for j in range(idx)), (
                        f"non-VIP appears before VIP in {bucket}"
                    )
                    break
    finally:
        requests.patch(
            f"{BASE}/api/clients/{cid}/tier",
            json={"tier": ""},
            headers=H(token),
            timeout=10,
        )
