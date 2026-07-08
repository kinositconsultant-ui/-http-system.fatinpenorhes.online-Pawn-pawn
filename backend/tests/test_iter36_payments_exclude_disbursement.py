"""Iteration 36 — Reports must exclude disbursements from payment totals.

Disbursements are money going OUT to the client (the loan itself). They must
not be counted as payment activity coming IN. This test verifies both the
Payments report (rows + total_payments KPI) and the Financial report
(total_payment KPI) never include documents where type == "disbursement".
"""
from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def api_sess():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@fatinpenhores.tl", "password": "admin123"},
    )
    assert r.status_code == 200
    return s


def test_payments_report_excludes_disbursement_rows(api_sess):
    r = api_sess.get(f"{BASE_URL}/api/reports/v2/payments")
    assert r.status_code == 200
    data = r.json()
    disbursement_rows = [row for row in data["rows"] if row.get("type") == "disbursement"]
    assert not disbursement_rows, (
        f"Payments report should not include disbursement rows; found {len(disbursement_rows)}"
    )


def test_payments_report_total_matches_row_sum(api_sess):
    """The KPI must equal the sum of visible rows (proves nothing hidden was added)."""
    data = api_sess.get(f"{BASE_URL}/api/reports/v2/payments").json()
    total = round(sum(float(r.get("amount", 0) or 0) for r in data["rows"]), 2)
    assert data["kpis"]["total_payments"] == total, (
        f"KPI total_payments ({data['kpis']['total_payments']}) != sum of visible rows ({total})"
    )


def test_financial_report_total_payment_excludes_disbursement(api_sess):
    """total_payment on Financial report must match Payments report exactly."""
    p = api_sess.get(f"{BASE_URL}/api/reports/v2/payments").json()
    f = api_sess.get(f"{BASE_URL}/api/reports/v2/financial").json()
    assert f["kpis"]["total_payment"] == p["kpis"]["total_payments"], (
        f"Financial total_payment ({f['kpis']['total_payment']}) should equal "
        f"Payments total_payments ({p['kpis']['total_payments']})"
    )
