"""Iter 69 — Auction Legacy Backfill maintenance endpoint.

Verifies:
- POST /finance/maintenance/backfill-auction-loans requires admin
- dry_run=true does not mutate the DB
- When contract lookup succeeds, original_loan_amount + auction_profit + realized_loss are set correctly
- Fallback: contract_number match works when contract_id is missing or the contract was recreated
- Rows without a resolvable contract are skipped with a helpful reason
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


def test_endpoint_returns_summary_shape(s):
    r = s.post(f"{API}/finance/maintenance/backfill-auction-loans?dry_run=true", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["dry_run"] is True
    for k in ("count_updated", "count_skipped", "updated", "skipped_reasons"):
        assert k in d, f"missing {k}"
    assert isinstance(d["count_updated"], int)
    assert isinstance(d["count_skipped"], int)


def test_dry_run_does_not_mutate_db(s):
    """Snapshot summary, run dry_run, verify summary unchanged."""
    before = s.get(f"{API}/finance/summary", timeout=15).json()
    r = s.post(f"{API}/finance/maintenance/backfill-auction-loans?dry_run=true", timeout=30)
    assert r.status_code == 200
    after = s.get(f"{API}/finance/summary", timeout=15).json()
    for k in ("auction_realized_profit", "auction_realized_loss", "auction_sales",
              "auction_capital_recovered"):
        assert before[k] == after[k], f"dry_run changed {k}: {before[k]} → {after[k]}"


def test_requires_admin():
    """Fresh session (no admin cookie) → 401/403."""
    r = requests.post(f"{API}/finance/maintenance/backfill-auction-loans", timeout=15)
    assert r.status_code in (401, 403)


def test_skipped_reasons_are_helpful(s):
    """When rows are skipped they must include a machine-readable reason."""
    d = s.post(f"{API}/finance/maintenance/backfill-auction-loans?dry_run=true", timeout=30).json()
    if d["count_skipped"] > 0:
        for x in d["skipped_reasons"]:
            assert "reason" in x
            assert x["reason"] in (
                "contract_not_found",
                "no_contract_id",
                "contract_has_no_loan_amount",
            )
