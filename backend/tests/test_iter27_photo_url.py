"""Iteration 27 — Photo URL rendering fix (deployment bug).

Covers:
- fileUrl helper: verified via frontend playwright (see iter27 UI test).
- Client photo_url can be stored as: absolute URL, /api/files/... path, or storage key.
- Public verify endpoint returns photo_url as stored (no rewrite).
- Card PDF endpoint normalises storage-key photo_url before ReportLab fetch.
- PDF byte-stream is a valid %PDF regardless of photo_url shape (even if the
  embedded image fetch fails, ReportLab falls back to initials avatar).
- Regression: client with no photo_url still gets a valid PDF.
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"

# 1x1 PNG (transparent) — smallest valid PNG bytes
TINY_PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
    "0000000A49444154789C63000100000500010D0A2DB40000000049454E44AE426082"
)

PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", BASE_URL).rstrip("/")


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def uploaded_photo_key(admin):
    """Upload a real photo via /api/files/upload and return the resulting storage key."""
    files = {"file": ("test_photo.png", TINY_PNG, "image/png")}
    r = admin.post(f"{API}/upload", files=files, timeout=15)
    assert r.status_code in (200, 201), f"upload failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    # `storage_path` is the bare key; `url` is /api/files/<key>
    key = data.get("storage_path") or ""
    assert key, f"no storage_path in response: {data}"
    return key


def _create_client(admin, photo_url: str, tag: str) -> str:
    ts = int(time.time() * 1000)
    payload = {
        "full_name": f"TEST_Photo_{tag}_{ts}",
        "id_type": "BI",
        "id_number": f"PH-{tag}-{ts}",
        "phone": "77777777",
        "photo_url": photo_url,
    }
    r = admin.post(f"{API}/clients", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"client create failed: {r.status_code} {r.text[:200]}"
    return r.json()["id"]


class TestPhotoUrlShapes:
    """Verify /api/clients accepts all three photo_url shapes and echoes them back."""

    def test_storage_key_shape(self, admin, uploaded_photo_key):
        cid = _create_client(admin, uploaded_photo_key, "key")
        r = admin.get(f"{API}/clients/{cid}", timeout=15)
        assert r.status_code == 200
        assert r.json()["photo_url"] == uploaded_photo_key

    def test_api_path_shape(self, admin, uploaded_photo_key):
        api_path = f"/api/files/{uploaded_photo_key}"
        cid = _create_client(admin, api_path, "apipath")
        r = admin.get(f"{API}/clients/{cid}", timeout=15)
        assert r.status_code == 200
        assert r.json()["photo_url"] == api_path

    def test_absolute_url_shape(self, admin):
        abs_url = "https://example.com/photo.jpg"
        cid = _create_client(admin, abs_url, "abs")
        r = admin.get(f"{API}/clients/{cid}", timeout=15)
        assert r.status_code == 200
        assert r.json()["photo_url"] == abs_url


class TestCardPdfPhotoNormalisation:
    """The card-pdf endpoint should return a valid PDF for any photo_url shape."""

    def _issue_and_fetch_pdf(self, admin, cid: str) -> bytes:
        r = admin.post(f"{API}/clients/{cid}/issue-card", timeout=15)
        assert r.status_code == 200, r.text
        r = admin.get(f"{API}/clients/{cid}/card-pdf", timeout=30)
        assert r.status_code == 200, f"pdf fetch failed: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        return r.content

    def test_pdf_with_storage_key(self, admin, uploaded_photo_key):
        cid = _create_client(admin, uploaded_photo_key, "pdfkey")
        pdf = self._issue_and_fetch_pdf(admin, cid)
        assert pdf[:4] == b"%PDF", f"not a valid PDF header: {pdf[:20]!r}"
        assert len(pdf) > 1000, f"PDF too small ({len(pdf)} bytes) — likely broken"

    def test_pdf_with_api_path(self, admin, uploaded_photo_key):
        cid = _create_client(admin, f"/api/files/{uploaded_photo_key}", "pdfapi")
        pdf = self._issue_and_fetch_pdf(admin, cid)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 1000

    def test_pdf_with_absolute_url_unreachable(self, admin):
        # Unreachable absolute URL still yields a valid PDF (falls back to initials)
        cid = _create_client(admin, "https://nonexistent.invalid/x.jpg", "pdfabs")
        pdf = self._issue_and_fetch_pdf(admin, cid)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 1000

    def test_pdf_with_no_photo(self, admin):
        cid = _create_client(admin, "", "pdfnone")
        pdf = self._issue_and_fetch_pdf(admin, cid)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 1000


class TestPublicVerifyPhoto:
    """Public verify endpoint should return photo_url pointing at the new public
    photo endpoint (`/api/public/verify/{token}/photo`) so anonymous QR-scan
    visitors don't need auth cookies."""

    def test_verify_returns_public_photo_url(self, admin, uploaded_photo_key):
        cid = _create_client(admin, uploaded_photo_key, "verify")
        r = admin.post(f"{API}/clients/{cid}/issue-card", timeout=15)
        assert r.status_code == 200
        token = r.json()["member_verify_token"]

        # Public endpoint — no auth needed
        pub = requests.get(f"{API}/public/verify/{token}", timeout=15)
        assert pub.status_code == 200, pub.text
        data = pub.json()
        assert data.get("valid") is True
        photo_url = data.get("photo_url") or ""
        expected_suffix = f"/api/public/verify/{token}/photo"
        assert photo_url.endswith(expected_suffix), (
            f"expected photo_url to point at public verify-photo endpoint, got {photo_url!r}"
        )
        # Should be an absolute URL for anonymous browsers
        assert photo_url.startswith("http"), f"expected absolute URL, got {photo_url!r}"


class TestPublicVerifyPhotoEndpoint:
    """New: `/api/public/verify/{token}/photo` — no auth — streams client photo."""

    def test_photo_bytes_returned_for_storage_key(self, admin, uploaded_photo_key):
        cid = _create_client(admin, uploaded_photo_key, "pubphotokey")
        r = admin.post(f"{API}/clients/{cid}/issue-card", timeout=15)
        assert r.status_code == 200
        token = r.json()["member_verify_token"]

        # Anonymous fetch — brand new session, no cookies
        r = requests.get(f"{API}/public/verify/{token}/photo", timeout=15)
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("image/"), (
            f"expected image/*, got {r.headers.get('content-type')!r}"
        )
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n", (
            f"expected PNG magic bytes, got {r.content[:16]!r}"
        )

    def test_photo_redirect_for_absolute_url(self, admin):
        abs_url = "https://example.com/photo.jpg"
        cid = _create_client(admin, abs_url, "pubphotoabs")
        r = admin.post(f"{API}/clients/{cid}/issue-card", timeout=15)
        assert r.status_code == 200
        token = r.json()["member_verify_token"]

        # Anonymous fetch — do NOT follow redirect
        r = requests.get(f"{API}/public/verify/{token}/photo", timeout=15, allow_redirects=False)
        assert r.status_code in (301, 302, 303, 307, 308), (
            f"expected redirect for absolute-URL photo, got {r.status_code}: {r.text[:200]}"
        )
        assert r.headers.get("location") == abs_url, (
            f"expected Location: {abs_url}, got {r.headers.get('location')!r}"
        )

    def test_photo_404_for_unknown_token(self):
        # Long enough to pass the >=8 length check, but not a valid token
        r = requests.get(f"{API}/public/verify/notavalidtoken12345/photo", timeout=15)
        assert r.status_code == 404, f"expected 404 for unknown token, got {r.status_code}"

    def test_photo_404_for_short_token(self):
        r = requests.get(f"{API}/public/verify/short/photo", timeout=15)
        assert r.status_code == 404, f"expected 404 for short token, got {r.status_code}"


class TestPhotoEmbeddedInPdf:
    """Confirm the client photo is actually embedded in the PDF (not initials fallback).

    Compares PDF size for (a) client WITH photo_url=storage-key vs (b) client
    with no photo. If normalised URL fetch works, (a) should be meaningfully
    larger than (b) OR contain image count > baseline.

    KNOWN RISK: /api/files/... requires cookie auth — the server-side
    urllib.request.urlopen in build_member_card_pdf has NO cookies, so it will
    401 and silently fall back to initials. This test surfaces that regression.
    """

    def _mk_and_fetch(self, admin, photo_url: str, tag: str) -> bytes:
        cid = _create_client(admin, photo_url, tag)
        admin.post(f"{API}/clients/{cid}/issue-card", timeout=15)
        r = admin.get(f"{API}/clients/{cid}/card-pdf", timeout=30)
        assert r.status_code == 200
        return r.content

    def test_pdf_photo_larger_than_initials_only(self, admin, uploaded_photo_key):
        pdf_no_photo = self._mk_and_fetch(admin, "", "cmpnone")
        pdf_with_photo = self._mk_and_fetch(admin, uploaded_photo_key, "cmpkey")
        # If the photo was actually embedded, the PDF should be noticeably
        # larger (image XObject + PNG stream). If not, sizes will be nearly
        # identical (both just render initials).
        delta = len(pdf_with_photo) - len(pdf_no_photo)
        # Even a 1x1 PNG adds a few hundred bytes as an XObject; anything <200
        # bytes strongly implies fallback path (no photo embedded).
        assert delta > 200, (
            f"PDF with storage-key photo_url ({len(pdf_with_photo)}B) is not "
            f"meaningfully larger than PDF with no photo ({len(pdf_no_photo)}B) — "
            f"delta={delta}B. This means ReportLab could NOT fetch the photo "
            "(likely 401 from protected /api/files endpoint). The 'photo in PDF' "
            "fix is incomplete — need to make file endpoint public for known "
            "clients OR pass an ?auth=<token> query param when normalising URL."
        )
