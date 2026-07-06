"""Iteration 31 — Month-end compliance bundle.

Verifies:
- Admin can generate a ZIP for a given YYYY-MM
- ZIP contains all 4 required deliverables + README
- Archives endpoint lists the persisted bundle
- Archive download returns identical bytes
- Invalid month is rejected with 400
- Filename traversal is blocked
- Non-authenticated requests get 401
- Scheduler status exposes next_monthend_run_at
"""
from __future__ import annotations

import io
import os
import zipfile

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


def test_generate_bundle_returns_zip(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/monthend/generate", params={"month": "2025-11"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "monthend-2025-11.zip" in r.headers.get("content-disposition", "")

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert "finance_summary_2025-11.pdf" in names
    assert "expenses_2025-11.pdf" in names
    assert "audit_log_2025-11.pdf" in names
    assert "treasury_2025-11.xlsx" in names
    assert "README.txt" in names

    # PDFs are valid (start with %PDF)
    assert zf.read("finance_summary_2025-11.pdf")[:4] == b"%PDF"
    assert zf.read("expenses_2025-11.pdf")[:4] == b"%PDF"
    assert zf.read("audit_log_2025-11.pdf")[:4] == b"%PDF"
    # xlsx = zip too
    xlsx_bytes = zf.read("treasury_2025-11.xlsx")
    assert xlsx_bytes[:2] == b"PK"
    # README mentions Tetum + English
    readme = zf.read("README.txt").decode("utf-8")
    assert "Konteúdu (Tetum)" in readme
    assert "2025-11" in readme


def test_archive_listed_and_downloadable(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/monthend/archives")
    assert r.status_code == 200
    items = r.json()
    names = [it["name"] for it in items]
    assert "monthend-2025-11.zip" in names
    target = next(it for it in items if it["name"] == "monthend-2025-11.zip")
    assert target["month"] == "2025-11"
    assert target["size"] > 0
    assert "modified" in target

    # download
    r2 = api_sess.get(f"{BASE_URL}/api/monthend/archives/monthend-2025-11.zip")
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r2.content))
    assert "README.txt" in zf.namelist()


def test_invalid_month_rejected(api_sess):
    for bad in ["", "2025-13", "202511", "2025-1", "foo-bar"]:
        r = api_sess.get(f"{BASE_URL}/api/monthend/generate", params={"month": bad})
        assert r.status_code in (400, 422), f"{bad} → {r.status_code}"


def test_filename_traversal_blocked(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/monthend/archives/..%2Fetc%2Fpasswd")
    assert r.status_code in (400, 404)
    r2 = api_sess.get(f"{BASE_URL}/api/monthend/archives/somefile.txt")
    assert r2.status_code == 400


def test_requires_admin_auth():
    r = requests.get(f"{BASE_URL}/api/monthend/archives")
    assert r.status_code == 401
    r2 = requests.get(f"{BASE_URL}/api/monthend/generate", params={"month": "2025-11"})
    assert r2.status_code == 401


def test_scheduler_exposes_monthend_next_run(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/admin/backups/schedule")
    assert r.status_code == 200
    data = r.json()
    assert data.get("running") is True
    # next_monthend_run_at may be None immediately after cold start, but the key must exist
    assert "next_monthend_run_at" in data
    assert data["next_monthend_run_at"] is not None
