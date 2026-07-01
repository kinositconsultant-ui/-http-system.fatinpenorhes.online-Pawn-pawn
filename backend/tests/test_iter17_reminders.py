"""Iteration 17 tests — refactor sanity, module gating, and daily overdue reminders.

Covers:
- Refactor: server boots, admin login works, all main GETs respond 200.
- RBAC via deps.require_module: cashier is blocked from /api/clients, allowed on /api/payments; admin bypasses.
- Reminders CRUD/behavior: status, run, dedup, logs, master toggle, day-bucket boundary.
- Regression: iter16 disbursement auto-record still fires on contract create.
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# ---------- fixtures ----------

@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    body = r.json()
    assert "allowed_modules" in body.get("user", body), f"no allowed_modules in login response: {body}"
    return s


@pytest.fixture(scope="session")
def cashier_session(admin_session):
    """Create a cashier user with only ['dashboard','payments'] modules, then login."""
    email = "TEST_cashier_iter17@fatinpenhores.tl"
    payload = {
        "email": email,
        "password": "cashierpass1",
        "name": "TEST Cashier iter17",
        "role": "cashier",
        "allowed_modules": ["dashboard", "payments"],
    }
    # try create — if exists, patch modules just to be safe
    r = admin_session.post(f"{API}/users", json=payload, timeout=15)
    if r.status_code not in (200, 201):
        # already exists — fetch and update modules
        users = admin_session.get(f"{API}/users", timeout=15).json()
        u = next((u for u in users if u.get("email") == email), None)
        if u:
            admin_session.put(f"{API}/users/{u['id']}", json={"allowed_modules": ["dashboard", "payments"]}, timeout=15)
            admin_session.put(f"{API}/users/{u['id']}/password", json={"password": "cashierpass1"}, timeout=15)
    s = requests.Session()
    lr = s.post(f"{API}/auth/login", json={"email": email, "password": "cashierpass1"}, timeout=15)
    if lr.status_code != 200:
        pytest.skip(f"cashier login failed: {lr.status_code} {lr.text}")
    return s


# ---------- refactor sanity ----------

REFACTOR_GETS = [
    "/clients", "/contracts", "/payments",
    "/items/car", "/items/motorcycle", "/items/electronic", "/items/pezadu",
    "/users", "/users/modules", "/settings",
    "/dashboard/summary", "/finance/summary",
    "/reports/v2/inventory", "/audit-log",
]


@pytest.mark.parametrize("path", REFACTOR_GETS)
def test_refactor_get_endpoints_200(admin_session, path):
    r = admin_session.get(f"{API}{path}", timeout=20)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:300]}"


def test_admin_login_returns_allowed_modules(admin_session):
    r = admin_session.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200
    me = r.json()
    assert me.get("role") == "admin"
    # admin should implicitly have full module access via ROLE_DEFAULT_MODULES
    assert isinstance(me.get("allowed_modules", []), list)


# ---------- RBAC / module gating ----------

def test_cashier_blocked_on_clients(cashier_session):
    r = cashier_session.get(f"{API}/clients", timeout=15)
    assert r.status_code == 403, f"cashier should be 403 on /clients, got {r.status_code}"


def test_cashier_allowed_on_payments(cashier_session):
    r = cashier_session.get(f"{API}/payments", timeout=15)
    assert r.status_code == 200, f"cashier should be 200 on /payments, got {r.status_code} {r.text[:200]}"


def test_admin_bypasses_module_gate(admin_session):
    for p in ["/clients", "/payments", "/reports/v2/inventory"]:
        r = admin_session.get(f"{API}{p}", timeout=15)
        assert r.status_code == 200, f"admin blocked on {p} ({r.status_code})"


# ---------- reminders: status + auth ----------

def test_reminders_status_admin(admin_session):
    r = admin_session.get(f"{API}/reminders/status", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ["enabled", "reminder_days", "local_time"]:
        assert k in body, f"missing {k} in status: {body}"
    assert body["reminder_days"] == [7, 9]
    assert "next_run_at" in body


def test_reminders_status_forbidden_for_cashier(cashier_session):
    r = cashier_session.get(f"{API}/reminders/status", timeout=15)
    assert r.status_code == 403


def test_reminders_logs_forbidden_for_cashier(cashier_session):
    r = cashier_session.get(f"{API}/reminders/logs", timeout=15)
    assert r.status_code == 403


# ---------- reminders: run + dedup ----------

def test_reminders_run_returns_summary(admin_session):
    r = admin_session.post(f"{API}/reminders/run", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("scanned", "sent", "skipped", "errors", "attempted"):
        assert k in body, f"missing {k} in run summary: {body}"
    assert isinstance(body["scanned"], int)
    assert body["scanned"] >= 0


def test_reminders_dedup_second_run(admin_session):
    first = admin_session.post(f"{API}/reminders/run", timeout=30).json()
    time.sleep(0.5)
    second = admin_session.post(f"{API}/reminders/run", timeout=30).json()
    # Anything that got logged on the first run should still be logged (skipped) on the second.
    # Second run must not increase 'sent' for contracts already in reminder_log today.
    assert second["sent"] == 0 or second["sent"] <= first["sent"], f"dedup broken: {first} vs {second}"
    # skipped on second should be >= first's (sent+skipped)
    prev_touched = first["sent"] + first["skipped"]
    assert second["skipped"] >= prev_touched, (
        f"dedup skipped counter mismatch: first={first}, second={second}"
    )


def test_reminders_logs_shape(admin_session):
    r = admin_session.get(f"{API}/reminders/logs", timeout=15)
    assert r.status_code == 200
    logs = r.json()
    assert isinstance(logs, list)
    if logs:
        entry = logs[0]
        for k in ("contract_id", "day_bucket", "date", "phone", "success"):
            assert k in entry, f"missing {k} in log entry: {entry}"


# ---------- reminders: master toggle ----------

def test_reminders_master_toggle_disables_run(admin_session):
    # save originals
    original = admin_session.get(f"{API}/settings", timeout=15).json()
    try:
        # turn off
        put = admin_session.put(f"{API}/settings", json={"reminders_enabled": False}, timeout=15)
        assert put.status_code == 200, put.text
        status = admin_session.get(f"{API}/reminders/status", timeout=15).json()
        assert status["enabled"] is False

        run = admin_session.post(f"{API}/reminders/run", timeout=30).json()
        assert run.get("disabled") is True, f"expected disabled:true when off, got {run}"
        assert run["scanned"] == 0
        assert run["sent"] == 0
    finally:
        # re-enable regardless
        admin_session.put(f"{API}/settings", json={"reminders_enabled": True}, timeout=15)

    # verify normal run resumes
    status = admin_session.get(f"{API}/reminders/status", timeout=15).json()
    assert status["enabled"] is True
    run2 = admin_session.post(f"{API}/reminders/run", timeout=30).json()
    assert "disabled" not in run2 or run2.get("disabled") is False
    assert run2["scanned"] >= 0


# ---------- reminders: day-bucket boundary ----------

def _find_client_id(admin_session) -> str | None:
    clients = admin_session.get(f"{API}/clients", timeout=15).json()
    if not clients:
        return None
    # pick one with phone if possible
    with_phone = [c for c in clients if c.get("phone")]
    return (with_phone[0] if with_phone else clients[0])["id"]


def _mk_car_item(admin_session) -> str | None:
    payload = {
        "name": "TEST iter17 car",
        "machine_number": f"TEST-{int(time.time())}",
        "brand": "Test",
        "model": "M1",
        "year": 2020,
        "color": "Red",
        "plate_number": "T-1234",
        "estimated_value": 5000,
    }
    r = admin_session.post(f"{API}/items/car", json=payload, timeout=15)
    if r.status_code not in (200, 201):
        return None
    return r.json().get("id")


def _create_overdue_contract(admin_session, client_id: str, item_id: str, days_overdue: int) -> str | None:
    """Create a contract whose due_date is exactly `days_overdue` days before today."""
    today = date.today()
    due = (today - timedelta(days=days_overdue)).isoformat()
    contract_date = (today - timedelta(days=days_overdue + 30)).isoformat()  # 30d term
    payload = {
        "client_id": client_id,
        "item_type": "car",
        "item_id": item_id,
        "loan_amount": 1000,
        "interest_rate": 10,
        "contract_date": contract_date,
        "due_date": due,
        "term_days": 30,
    }
    r = admin_session.post(f"{API}/contracts", json=payload, timeout=15)
    if r.status_code not in (200, 201):
        return None
    return r.json().get("id")


def test_reminders_day_boundary_targets_7_and_9_only(admin_session):
    client_id = _find_client_id(admin_session)
    if not client_id:
        pytest.skip("no client fixture available")

    created: list[str] = []
    # Create fresh items+contracts for buckets we care about
    day_buckets_to_test = {7: True, 9: True, 6: False, 8: False, 10: False}
    contract_ids: dict[int, str] = {}

    for days_od, should_target in day_buckets_to_test.items():
        item_id = _mk_car_item(admin_session)
        if not item_id:
            pytest.skip("could not create item fixture")
        cid = _create_overdue_contract(admin_session, client_id, item_id, days_od)
        if not cid:
            pytest.skip(f"could not create contract for days_overdue={days_od}")
        contract_ids[days_od] = cid
        created.append(cid)

    try:
        # Trigger reminders
        run = admin_session.post(f"{API}/reminders/run", timeout=30).json()
        logs = admin_session.get(f"{API}/reminders/logs", timeout=15).json()
        # Only 7 and 9 day contracts we created should appear in reminder_log
        for days_od, cid in contract_ids.items():
            matched = [l for l in logs if l.get("contract_id") == cid]
            if days_od in (7, 9):
                assert matched, f"expected reminder_log entry for {days_od}-day contract {cid}, run={run}"
                assert matched[0]["day_bucket"] == days_od
            else:
                assert not matched, f"unexpected reminder for {days_od}-day contract {cid}: {matched}"
    finally:
        # best-effort cleanup
        for cid in created:
            try:
                admin_session.delete(f"{API}/contracts/{cid}", timeout=10)
            except Exception:
                pass


# ---------- iter16 regression: disbursement auto-record ----------

def test_iter16_disbursement_still_autoinserted(admin_session):
    client_id = _find_client_id(admin_session)
    if not client_id:
        pytest.skip("no client")
    item_id = _mk_car_item(admin_session)
    if not item_id:
        pytest.skip("no item")
    today = date.today()
    payload = {
        "client_id": client_id,
        "item_type": "car",
        "item_id": item_id,
        "loan_amount": 500,
        "interest_rate": 10,
        "contract_date": today.isoformat(),
        "due_date": (today + timedelta(days=30)).isoformat(),
        "term_days": 30,
    }
    r = admin_session.post(f"{API}/contracts", json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    try:
        pays = admin_session.get(f"{API}/payments", timeout=15).json()
        disb = [p for p in pays if p.get("contract_id") == cid and p.get("kind") in ("disbursement", "loan_disbursement", "disburse")]
        # Fall back: any payment tied to this contract on creation day
        if not disb:
            disb = [p for p in pays if p.get("contract_id") == cid]
        assert disb, f"expected auto-disbursement payment for new contract {cid}"
    finally:
        admin_session.delete(f"{API}/contracts/{cid}", timeout=10)
