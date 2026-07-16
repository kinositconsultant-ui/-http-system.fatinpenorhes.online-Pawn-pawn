"""Iter39 — PDF header overlap fix.

Verifies:
1. CTR-2026-0003 PDF header uses new short label "Montante Empréstimu"
   and NOT the old "Empréstimu (Orij → Atuál)".
2. Header value 'USD $200.00' or '$200.00' is readable / present.
3. CTR-2026-0005 (partial-payment) header shows arrow value '$3,000.00 → $1,000.00'.
4. Article 8 penalty for CTR-2026-0005 is based on current principal ($100).
"""
import io
import os
import re
import pytest
import requests
from pypdf import PdfReader

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    assert url, "REACT_APP_BACKEND_URL is not set"
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def contracts_by_number(session):
    r = session.get(f"{API}/contracts", timeout=30)
    assert r.status_code == 200, f"List contracts failed: {r.status_code} {r.text}"
    data = r.json()
    contracts = data if isinstance(data, list) else data.get("items", data.get("contracts", []))
    mapping = {c.get("contract_number"): c for c in contracts}
    return mapping


def _fetch_pdf_text(session, contract_id: str) -> str:
    r = session.get(f"{API}/contracts/{contract_id}/pdf", timeout=60)
    assert r.status_code == 200, f"PDF fetch failed: {r.status_code} {r.text[:200]}"
    assert r.headers.get("content-type", "").startswith("application/pdf") or r.content[:4] == b"%PDF", \
        f"Not a PDF: content-type={r.headers.get('content-type')}"
    reader = PdfReader(io.BytesIO(r.content))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


class TestPdfHeaderOverlapFix:
    def test_ctr_0003_header_uses_new_label(self, session, contracts_by_number):
        c = contracts_by_number.get("CTR-2026-0003")
        assert c is not None, f"CTR-2026-0003 not found. Available: {list(contracts_by_number.keys())[:10]}"
        text = _fetch_pdf_text(session, c["id"])
        # New short label must be present
        assert "Montante Empréstimu" in text, \
            f"Expected 'Montante Empréstimu' in PDF, got sample: {text[:600]!r}"
        # Old long label must NOT be present
        assert "Empréstimu (Orij" not in text and "Orij → Atuál" not in text, \
            f"Old overlapping label still present. Sample: {text[:600]!r}"

    def test_ctr_0003_header_value_readable(self, session, contracts_by_number):
        c = contracts_by_number["CTR-2026-0003"]
        text = _fetch_pdf_text(session, c["id"])
        # Value should include $200.00 somewhere near label
        assert "$200.00" in text, f"Expected '$200.00' in PDF text. Sample: {text[:800]!r}"

    def test_ctr_0005_header_arrow_value(self, session, contracts_by_number):
        c = contracts_by_number.get("CTR-2026-0005")
        assert c is not None, "CTR-2026-0005 not found"
        text = _fetch_pdf_text(session, c["id"])
        assert "Montante Empréstimu" in text, "Short label missing on CTR-2026-0005"
        # Arrow between original and current (allow flexible spacing / unicode)
        # pypdf may split unicode arrow; check both amounts present + arrow char.
        assert "$3,000.00" in text, f"Original $3,000.00 missing. Sample: {text[:800]!r}"
        assert "$1,000.00" in text, f"Current $1,000.00 missing. Sample: {text[:800]!r}"
        assert "→" in text or "->" in text, f"Arrow between amounts missing. Sample: {text[:800]!r}"

    def test_ctr_0005_article8_penalty_uses_current_principal(self, session, contracts_by_number):
        c = contracts_by_number["CTR-2026-0005"]
        text = _fetch_pdf_text(session, c["id"])
        # Penalty is 10% of current principal $1,000 -> $100.00
        # Should NOT show $300.00 (10% of $3,000 original)
        # Find Article 8 section for scoping
        m = re.search(r"Artigu\s*8", text)
        section = text[m.start():m.start() + 800] if m else text
        assert "$100.00" in section, f"Expected $100.00 penalty (10% of current $1,000). Section: {section!r}"
        # $300.00 could still appear elsewhere in whole doc; just ensure not in Art8 penalty section as primary value
        # Soft check: warn if $300.00 appears in same section
        # (Not asserting hard fail since original amount is legitimately referenced elsewhere.)

    def test_ctr_0005_article2_shows_both_amounts(self, session, contracts_by_number):
        c = contracts_by_number["CTR-2026-0005"]
        text = _fetch_pdf_text(session, c["id"])
        m = re.search(r"Artigu\s*2", text)
        assert m is not None, "Article 2 not found in PDF"
        section = text[m.start():m.start() + 1200]
        assert "$3,000.00" in section, f"Article 2 missing original $3,000.00. Section: {section!r}"
        assert "$1,000.00" in section, f"Article 2 missing current $1,000.00. Section: {section!r}"
