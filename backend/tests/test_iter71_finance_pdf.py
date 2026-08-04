"""Iter 71 — Finance Summary PDF rebuilt to match iter61 Income Statement layout.

Verifies:
- KPI block now exposes capital_repaid_principal, capital_interest_paid,
  operating_expenses, financial_expenses, auction_net_profit
- New dedicated 5-row Income Statement section renders
- Math holds: Gross − Operating = Operating Profit; Operating Profit − Financial = Net
- Valid PDF magic bytes + size sanity
"""
import io
import os
import re
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


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extract ASCII-decodable content from a ReportLab-generated PDF for text
    presence checks. ReportLab flates text streams so full extraction requires
    a real PDF library. Here we settle for looking at BT ... ET blocks which
    contain the Tj/TJ operators."""
    try:
        import PyPDF2  # type: ignore
        r = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join(p.extract_text() or "" for p in r.pages)
    except ImportError:
        try:
            from pypdf import PdfReader  # type: ignore
            r = PdfReader(io.BytesIO(pdf_bytes))
            return "\n".join(p.extract_text() or "" for p in r.pages)
        except ImportError:
            pytest.skip("Neither PyPDF2 nor pypdf installed — cannot inspect PDF text")


def test_finance_summary_pdf_returns_valid_pdf(s):
    r = s.get(f"{API}/finance/summary/export/pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 5000


def test_finance_summary_pdf_contains_income_statement_section(s):
    """Full-text extraction (if a PDF library is available) confirms the new
    section header and each of the 5 Income Statement rows."""
    r = s.get(f"{API}/finance/summary/export/pdf", timeout=30)
    assert r.status_code == 200
    text = _pdf_text(r.content)
    # Look for the section title and each row label
    assert "Income Statement" in text, "Missing 'Income Statement' section title"
    assert "Gross Profit" in text
    assert "Operating Expenses" in text
    assert "Operating Profit" in text
    assert "Financial Expenses" in text
    assert "Net Profit" in text
    assert "Margin" in text


def test_finance_summary_pdf_has_new_kpi_rows(s):
    """New Key Indicators rows introduced in iter71."""
    r = s.get(f"{API}/finance/summary/export/pdf", timeout=30)
    text = _pdf_text(r.content)
    assert "Capital Repaid (Principal)" in text
    assert "Capital Interest Paid" in text
    assert "Auction Profit (net)" in text


def test_income_statement_math_reconciles(s):
    """The values on the summary MUST satisfy the Income Statement identity."""
    d = s.get(f"{API}/finance/summary", timeout=15).json()
    gross = float(d["gross_profit"])
    op_exp = float(d["operating_expenses"])
    op_profit = float(d["operating_profit"])
    fin_exp = float(d["financial_expenses"])
    net = float(d["net_profit"])
    assert round(gross - op_exp, 2) == pytest.approx(round(op_profit, 2), abs=0.01)
    assert round(op_profit - fin_exp, 2) == pytest.approx(round(net, 2), abs=0.01)
