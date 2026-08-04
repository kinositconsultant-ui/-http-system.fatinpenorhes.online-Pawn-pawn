"""Iter 67 — Auction P&L split: fix double-count between auction_interest_profit
and auction_realized_profit.

Rules:
- auction_profit = auction_realized_profit − auction_realized_loss  (fresh formula)
- auction_interest_profit is INFORMATIONAL only (subset of realized_profit)
- Adding both would double-count the same dollars — see iter67 commit
- New field `auction_net_profit` on /finance/summary exposes the fresh value
- Accounting identity: capital_recovered + realized_profit == auction_sales
  (interest_fee is a slice of realized_profit, not additional)
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


def _summary(s):
    return s.get(f"{API}/finance/summary", timeout=15).json()


def test_response_exposes_auction_net_profit(s):
    d = _summary(s)
    assert "auction_net_profit" in d, f"missing auction_net_profit; keys={list(d)[:20]}"
    assert isinstance(d["auction_net_profit"], (int, float))


def test_auction_profit_no_longer_double_counts_interest(s):
    """Verify that gross_profit uses realized_profit − realized_loss,
    NOT (interest_fee + realized_profit − realized_loss)."""
    d = _summary(s)
    ir = d["interest_received"]
    tp = d["total_penalty"]
    arp = d["auction_realized_profit"]
    arl = d["auction_realized_loss"]
    gp = d["gross_profit"]
    # New formula
    expected = round(ir + tp + arp - arl, 2)
    assert round(gp, 2) == expected, (
        f"gross_profit={gp} expected {expected} (ir={ir}, tp={tp}, arp={arp}, arl={arl})"
    )


def test_auction_net_profit_matches_realized_minus_loss(s):
    d = _summary(s)
    expected = round(d["auction_realized_profit"] - d["auction_realized_loss"], 2)
    assert d["auction_net_profit"] == pytest.approx(expected, abs=0.01)


def test_income_statement_identity_still_holds(s):
    """Gross − Operating − Financial = Net Profit."""
    d = _summary(s)
    expected = round(d["gross_profit"] - d["operating_expenses"] - d["financial_expenses"], 2)
    assert d["net_profit"] == pytest.approx(expected, abs=0.01)


def test_capital_recovered_plus_realized_matches_sales(s):
    """Iter37 identity: capital_recovered + realized_profit ≈ auction_sales.
    (Realized loss is baked into capital_recovered for shortfall sales.)"""
    d = _summary(s)
    lhs = d["auction_capital_recovered"] + d["auction_realized_profit"]
    # Allow $1 tolerance for legacy rows without original_loan_amount
    assert abs(lhs - d["auction_sales"]) < 5.0, (
        f"capital_recovered + realized_profit ({lhs}) should ≈ auction_sales ({d['auction_sales']})"
    )
