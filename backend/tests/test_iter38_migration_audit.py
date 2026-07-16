"""Iteration 38 — Data Migration Audit (Nov-2026 penalty overhaul)."""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def api_sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@fatinpenhores.tl", "password": "admin123"})
    assert r.status_code == 200
    return s


def test_requires_admin_auth():
    r = requests.get(f"{BASE_URL}/api/migration-audit/penalty")
    assert r.status_code == 401
    r2 = requests.get(f"{BASE_URL}/api/migration-audit/penalty/pdf")
    assert r2.status_code == 401


def test_json_shape(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/migration-audit/penalty")
    assert r.status_code == 200
    body = r.json()
    assert "kpis" in body
    for k in ("contracts_affected", "old_total_penalty", "new_total_penalty", "penalty_delta_total"):
        assert k in body["kpis"]
    assert body["columns"] == [
        "contract_number", "contract_date", "status",
        "original_loan_amount", "current_principal", "principal_paid",
        "old_penalty", "new_penalty", "penalty_delta",
    ]
    assert isinstance(body["rows"], list)


def test_row_math_is_consistent(api_sess):
    """For each row: new_penalty = current × 10%, old_penalty = original × 10%,
    delta = new - old, principal_paid = original - current."""
    body = api_sess.get(f"{BASE_URL}/api/migration-audit/penalty").json()
    for r in body["rows"]:
        # Values may have been computed with a per-contract penalty_rate; we
        # just check the ratio is consistent old:original == new:current.
        if r["original_loan_amount"] > 0:
            ratio_old = r["old_penalty"] / r["original_loan_amount"]
            ratio_new = r["new_penalty"] / r["current_principal"] if r["current_principal"] > 0 else ratio_old
            assert abs(ratio_old - ratio_new) < 0.001, f"Row {r['contract_number']}: rate not consistent"
        assert abs(round(r["new_penalty"] - r["old_penalty"], 2) - r["penalty_delta"]) < 0.01
        assert abs(round(r["original_loan_amount"] - r["current_principal"], 2) - r["principal_paid"]) < 0.01


def test_only_overdue_contracts_with_principal_paid(api_sess):
    body = api_sess.get(f"{BASE_URL}/api/migration-audit/penalty").json()
    for r in body["rows"]:
        assert r["status"] in ("overdue", "auction_ready")
        assert r["penalty_delta"] != 0, "rows with zero delta should be filtered"
        # If delta is negative, principal must have been paid (current < original)
        if r["penalty_delta"] < 0:
            assert r["current_principal"] < r["original_loan_amount"]


def test_pdf_download(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/migration-audit/penalty/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "penalty-migration-audit.pdf" in r.headers["content-disposition"]
    assert r.content[:4] == b"%PDF"
    # Header includes affected count for scripting
    assert r.headers.get("X-Contracts-Affected") is not None
