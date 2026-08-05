"""
iter73 — Finance PDF Auction Revenue Breakdown section
Presentation-only: verify PDF export contains the new section and that
GET /api/finance/summary still exposes all pre-existing keys.
"""
import io
import os
import re
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://pawnly-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


def test_summary_fields_unchanged(admin_session):
    r = admin_session.get(f"{API}/finance/summary", timeout=30)
    assert r.status_code == 200
    data = r.json()
    for key in [
        "auction_sales",
        "auction_capital_recovered",
        "auction_realized_profit",
        "auction_realized_loss",
        "auction_net_profit",
        "gross_profit",
        "operating_profit",
        "net_profit",
        "operating_expenses",
        "financial_expenses",
    ]:
        assert key in data, f"missing key {key} in /finance/summary"


def test_finance_pdf_contains_auction_breakdown(admin_session):
    r = admin_session.get(f"{API}/finance/summary/export/pdf", timeout=60)
    assert r.status_code == 200, f"PDF export failed {r.status_code}"
    content = r.content
    assert content[:4] == b"%PDF", "not a valid PDF (missing magic bytes)"
    assert len(content) > 5000, f"PDF too small ({len(content)} bytes)"

    # Extract text
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # fallback

    reader = PdfReader(io.BytesIO(content))
    text = ""
    for page in reader.pages:
        try:
            text += page.extract_text() or ""
        except Exception:
            pass

    # Normalize whitespace
    norm = re.sub(r"\s+", " ", text)

    required_snippets = [
        "Auction Revenue Breakdown",
        "Total Revenue from Auctions",
        "Loan Principal Recovered",
        "Auction Profit",       # "Auction Profit (Surplus)"
        "Realized Loss",        # "Realized Loss (Shortfall)"
        "NET Auction Profit",
        "Cash on Hand",         # identity footer
    ]
    missing = [s for s in required_snippets if s not in norm]
    assert not missing, f"missing snippets in finance PDF: {missing}\n---text---\n{norm[:2000]}"
