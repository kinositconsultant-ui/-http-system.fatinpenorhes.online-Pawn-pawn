"""iter76 — verifies the contracts / payments / auctions split from server.py.

After Phase-3 refactor, all `/contracts/*`, `/payments/*`, `/auctions/*` and
`/invoices/*` endpoints live in dedicated `routes/` modules. This suite
exercises one endpoint per module to catch registration mistakes.
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


def _headers(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def test_contracts_list_works(token: str):
    r = requests.get(f"{BASE}/api/contracts", headers=_headers(token), timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


def test_contracts_labels_pdf_wins_over_cid(token: str):
    """Route ordering — `labels-pdf` must resolve BEFORE `{cid}`."""
    r = requests.get(
        f"{BASE}/api/contracts/labels-pdf?status=active",
        headers=_headers(token),
        timeout=20,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


def test_payments_list_and_pdf(token: str):
    r = requests.get(f"{BASE}/api/payments", headers=_headers(token), timeout=15)
    assert r.status_code == 200
    payments = r.json()
    if payments:
        pid = payments[0]["id"]
        r2 = requests.get(
            f"{BASE}/api/payments/{pid}/pdf", headers=_headers(token), timeout=20
        )
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("application/pdf")


def test_auctions_and_invoices(token: str):
    r = requests.get(f"{BASE}/api/auctions", headers=_headers(token), timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{BASE}/api/invoices", headers=_headers(token), timeout=15)
    assert r.status_code == 200


def test_auction_catalogue_pdf_still_served(token: str):
    """Catalogue cache moved from server.py -> routes/auctions.py — verify
    the endpoint and lazy imports (scheduler + public route) still work.
    """
    r = requests.get(
        f"{BASE}/api/auctions/catalogue/pdf",
        headers=_headers(token),
        timeout=30,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
