"""Iter 68 — Auction Bulk Report (JSON + PDF).

Verifies:
- GET /finance/auction-report returns totals + top_gainers + top_losers + monthly
- Sums reconcile with /finance/summary (auction_realized_profit, auction_realized_loss)
- Filter by year narrows the dataset
- PDF endpoint returns valid PDF
- 401/403 without auth
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


def test_report_shape(s):
    r = s.get(f"{API}/finance/auction-report", timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ("period_label", "totals", "top_gainers", "top_losers", "monthly"):
        assert k in d, f"missing {k}"
    for k in ("count", "sales", "capital_recovered", "realized_profit",
              "realized_loss", "net_pl", "recovery_ratio_pct"):
        assert k in d["totals"], f"missing totals.{k}"
    assert isinstance(d["top_gainers"], list)
    assert isinstance(d["top_losers"], list)
    assert isinstance(d["monthly"], list)


def test_totals_reconcile_with_summary(s):
    """Auction report totals must match /finance/summary aggregates."""
    report = s.get(f"{API}/finance/auction-report", timeout=15).json()
    summary = s.get(f"{API}/finance/summary", timeout=15).json()
    # Sales and realized_profit / realized_loss should match to the cent.
    assert report["totals"]["realized_profit"] == pytest.approx(summary["auction_realized_profit"], abs=0.5)
    assert report["totals"]["realized_loss"] == pytest.approx(summary["auction_realized_loss"], abs=0.5)
    assert report["totals"]["net_pl"] == pytest.approx(summary["auction_net_profit"], abs=0.5)


def test_year_filter_narrows_dataset(s):
    """Report with year=2020 (before any records) should return count=0."""
    r = s.get(f"{API}/finance/auction-report?year=2020", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["totals"]["count"] == 0
    assert d["top_gainers"] == []
    assert d["top_losers"] == []
    assert d["period_label"] == "2020"


def test_top_gainers_sorted_desc(s):
    """When gainers exist, they must be sorted by gain descending (biggest first)."""
    d = s.get(f"{API}/finance/auction-report", timeout=15).json()
    gainers = d["top_gainers"]
    if len(gainers) >= 2:
        for i in range(len(gainers) - 1):
            assert gainers[i]["gain"] >= gainers[i + 1]["gain"], (
                f"Top gainers must be sorted desc: {[g['gain'] for g in gainers]}"
            )


def test_pdf_endpoint_returns_valid_pdf(s):
    r = s.get(f"{API}/finance/auction-report/pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 5000
    # Suggested filename includes the period label
    disp = r.headers.get("content-disposition", "")
    assert "auction-report-" in disp


def test_pdf_month_year_filter_still_returns_valid_pdf(s):
    r = s.get(f"{API}/finance/auction-report/pdf?year=2026&month=8", timeout=30)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_endpoint_requires_auth():
    """Fresh session, no cookies → 401/403."""
    r = requests.get(f"{API}/finance/auction-report", timeout=15)
    assert r.status_code in (401, 403)
    r = requests.get(f"{API}/finance/auction-report/pdf", timeout=15)
    assert r.status_code in (401, 403)
