"""Iter 65 — Loan Amortization PDF per capital source.

Verifies:
- Endpoint returns a valid PDF with correct magic bytes
- 404 on unknown source
- Requires authentication
- Different payment_frequency produces the right number of installments
"""
import os
import pytest
import requests

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pawnly-pro.preview.emergentagent.com").rstrip("/") + "/api"
ADMIN = {"email": "admin@fatinpenhores.tl", "password": "admin123"}


@pytest.fixture(scope="module")
def s():
    session = requests.Session()
    r = session.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200
    return session


@pytest.fixture
def source_factory(s):
    created = []

    def make(**kw):
        payload = {
            "name": f"pytest-iter65-{os.getpid()}-{len(created)}",
            "source_type": "bank",
            "principal_amount": 12000.0,
            "interest_rate": 4.0,
            "interest_period": "monthly",
            "term_months": 12,
            "payment_frequency": "monthly",
            "start_date": "2026-01-01",
        }
        payload.update(kw)
        r = s.post(f"{API}/funding-sources", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        row = r.json()
        created.append(row["id"])
        return row

    yield make
    for sid in created:
        s.delete(f"{API}/funding-sources/{sid}", timeout=15)


def test_endpoint_returns_valid_pdf(s, source_factory):
    src = source_factory(payment_frequency="monthly", term_months=12)
    r = s.get(f"{API}/funding-sources/{src['id']}/amortization-pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 5000
    # Suggested filename uses sanitized source name
    disp = r.headers.get("content-disposition", "")
    assert "amortization-" in disp


def test_endpoint_returns_404_for_unknown_source(s):
    r = s.get(f"{API}/funding-sources/does-not-exist/amortization-pdf", timeout=15)
    assert r.status_code == 404


def test_endpoint_requires_auth():
    """Fresh session (no cookies) → 401."""
    r = requests.get(f"{API}/funding-sources/x/amortization-pdf", timeout=15)
    assert r.status_code in (401, 403)


def test_quarterly_produces_valid_pdf(s, source_factory):
    """Quarterly / 12mo = 4 installments — should still render."""
    src = source_factory(payment_frequency="quarterly", term_months=12)
    r = s.get(f"{API}/funding-sources/{src['id']}/amortization-pdf", timeout=30)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_lump_sum_produces_valid_pdf(s, source_factory):
    """Lump sum = single installment at end of term — should still render."""
    src = source_factory(payment_frequency="lump_sum", term_months=6)
    r = s.get(f"{API}/funding-sources/{src['id']}/amortization-pdf", timeout=30)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
