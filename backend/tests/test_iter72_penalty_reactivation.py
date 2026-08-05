"""Iter 72 — Fix: penalty_paid preserved after contract reactivation.

Bug: `_compute_contract_state` in services.py used to gate the payment-walk
cap on `is_overdue`. After reactivation (`due_date` moved into the future),
`is_overdue = False` → cap = 0 → historical overdue_* payments never bucketed
into `penalty_paid` → Financial Report lost penalty income while the Business
Dashboard (which reads directly from db.payments) still showed it.

Fix (services.py:187): drop the `is_overdue` gate from `penalty_walk_cap`.
The cap now only depends on `contract.status != "auction"` and the ORIGINAL
loan × rate. Current-owed penalty (line 311) still correctly stays gated on
`is_overdue` so a non-overdue contract shows $0 owed penalty going forward.

Test approach — end-to-end:
1. Create client + contract that becomes overdue.
2. Client makes an overdue_penalty_only payment.
3. Snapshot the finance summary — penalty_paid reflects the payment.
4. Reactivate the contract (push due_date into the future).
5. Re-fetch finance summary — penalty_paid MUST be unchanged.
"""
import os
from datetime import date, timedelta

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


@pytest.fixture
def overdue_contract(s):
    """Create a client + electronic item + contract that starts overdue."""
    created = {"contract_id": None, "client_id": None, "item_id": None}

    # 1. Client
    client_resp = s.post(f"{API}/clients", json={
        "full_name": f"pytest-iter72-{os.getpid()}",
        "phone": "+67000000000",
        "id_type": "Electoral",
        "id_number": f"IT72-{os.getpid()}",
    }, timeout=15).json()
    created["client_id"] = client_resp["id"]

    # 2. Item — use a small electronic to avoid huge penalty amounts
    item_resp = s.post(f"{API}/items/electronic", json={
        "brand": "TestBrand",
        "category": "phone",
        "model": f"iter72-{os.getpid()}",
        "serial_number": f"pytest-{os.getpid()}",
        "condition": "good",
        "valuation": 1000.0,
        "status": "in_stock",
    }, timeout=15).json()
    created["item_id"] = item_resp["id"]

    # 3. Contract — start 90 days ago so it's overdue by ~60 days
    start = (date.today() - timedelta(days=90)).isoformat()
    due = (date.today() - timedelta(days=60)).isoformat()
    contract_resp = s.post(f"{API}/contracts", json={
        "client_id": created["client_id"],
        "item_type": "electronic",
        "item_id": created["item_id"],
        "loan_amount": 500.0,
        "interest_rate": 15.0,
        "period_days": 30,
        "contract_date": start,
        "due_date": due,
    }, timeout=15).json()
    created["contract_id"] = contract_resp["id"]

    yield created

    # Cleanup: delete contract → item → client (best effort)
    s.delete(f"{API}/contracts/{created['contract_id']}", timeout=15)
    s.delete(f"{API}/items/electronic/{created['item_id']}", timeout=15)
    s.delete(f"{API}/clients/{created['client_id']}", timeout=15)


def _summary_penalty(s):
    return float(s.get(f"{API}/finance/summary", timeout=15).json()["total_penalty"])


def test_penalty_survives_reactivation(s, overdue_contract):
    """Regression: penalty_paid MUST persist after reactivation."""
    cid = overdue_contract["contract_id"]

    # Before payment
    before = _summary_penalty(s)

    # Client pays penalty only — $50 (500 × 10% penalty × 1 month approx)
    pay = s.post(f"{API}/payments", json={
        "contract_id": cid,
        "amount": 50.0,
        "type": "overdue_penalty_only",
        "date": date.today().isoformat(),
        "notes": "iter72 test — penalty payment",
    }, timeout=15)
    assert pay.status_code == 200, pay.text

    after_pay = _summary_penalty(s)
    delta_after_pay = round(after_pay - before, 2)
    # Delta should be near $50 (some legacy state may cap; allow $30-$50)
    assert delta_after_pay >= 30, f"penalty did not register: before={before} after={after_pay}"

    # Reactivate contract with a new due date 30 days in the future
    new_due = (date.today() + timedelta(days=30)).isoformat()
    react = s.post(f"{API}/contracts/{cid}/reactivate", json={
        "new_due_date": new_due,
        "notes": "iter72 test reactivation",
    }, timeout=15)
    assert react.status_code == 200, react.text

    after_react = _summary_penalty(s)
    # THIS is the bug. Before iter72 fix, after_react ≪ after_pay (penalty vanished).
    assert after_react == pytest.approx(after_pay, abs=0.5), (
        f"iter72 REGRESSION: penalty vanished on reactivation. "
        f"before_pay={before}, after_pay={after_pay}, after_react={after_react}"
    )


def test_reactivation_does_not_add_new_penalty(s, overdue_contract):
    """Sanity: reactivation itself shouldn't introduce phantom penalty income."""
    cid = overdue_contract["contract_id"]
    before = _summary_penalty(s)
    new_due = (date.today() + timedelta(days=30)).isoformat()
    r = s.post(f"{API}/contracts/{cid}/reactivate", json={
        "new_due_date": new_due,
        "notes": "no payment reactivation",
    }, timeout=15)
    assert r.status_code == 200
    after = _summary_penalty(s)
    assert after == pytest.approx(before, abs=0.01), (
        f"reactivation-alone must not change penalty: before={before} after={after}"
    )
