"""Iter 63 — Capital Sources PDF: split principal/interest audit view."""
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


def test_capital_pdf_endpoint_returns_valid_pdf(s):
    r = s.get(f"{API}/finance/capital-sources/export/pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    body = r.content
    assert body[:4] == b"%PDF", "not a valid PDF"
    assert len(body) > 5000, "PDF suspiciously small"


def test_capital_pdf_contains_split_data(s):
    """Post a repayment then render — the PDF should embed the new columns
    and the repayment amounts should be reflected in the totals."""
    # Create source + $250 principal + $75 interest repayment
    src = s.post(f"{API}/funding-sources", json={
        "name": f"pytest-iter63-{os.getpid()}",
        "source_type": "bank",
        "principal_amount": 3000.0,
        "interest_rate": 4.0,
        "interest_period": "monthly",
        "term_months": 6,
        "start_date": "2026-01-01",
    }, timeout=15).json()

    try:
        s.post(f"{API}/funding-sources/{src['id']}/repayments", json={
            "source_id": src["id"], "principal_amount": 250, "interest_amount": 75,
            "date": "2026-02-04",
        }, timeout=15).raise_for_status()

        # Verify the LIST endpoint reflects the split (used by the PDF)
        listed = s.get(f"{API}/funding-sources", timeout=15).json()
        row = next(x for x in listed if x["id"] == src["id"])
        assert row["principal_paid"] == 250.0
        assert row["interest_paid"] == 75.0
        assert row["principal_remaining"] == 2750.0

        # PDF renders without error
        r = s.get(f"{API}/finance/capital-sources/export/pdf", timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
    finally:
        s.delete(f"{API}/funding-sources/{src['id']}", timeout=15)
