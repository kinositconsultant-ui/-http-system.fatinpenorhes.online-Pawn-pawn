"""Iteration 26 — Rule B (Hybrid interest) after partial payments.

Business rule:
- Month 1 interest = original loan × rate% (unchanged from Rule A)
- Month 2+ interest = REMAINING PRINCIPAL at the start of that month × rate%
- Only `partial` payments reduce the "principal at start of month" snapshot;
  close-out payments (`full`, `overdue_full`) arrive last and don't create new months.

Business owner example ($500 loan @ 10%, start Jan 10):
- Only 1 month elapsed → interest = $50 (Rule A anchor preserved).
- Partial $200 paid Jan 20 (still month 1). Then 2 months elapsed at Feb 11:
    * month 1 → $500 × 10% = $50
    * month 2 → ($500-$200) × 10% = $30
    * total interest = $80  (was $100 under Rule A — client is rewarded)
- Same partial paid Feb 20 (AFTER Feb 11 anniversary):
    * month 1 → $50, month 2 → $50 (partial arrived too late to reduce it)
    * month 3 starts Mar 11 → $30
    * total = $130 at 3 months (was $150 under Rule A)
"""
from __future__ import annotations

import asyncio
import uuid
import os
from datetime import date

from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from services import _recompute_contract_status  # noqa: E402
from deps import new_id, utcnow_iso  # noqa: E402


async def _seed_and_recompute(loan, rate, contract_date_iso, due_date_iso, payments):
    """Insert a contract + its payments and return the recomputed contract.

    Uses a fresh Motor client bound to the CURRENT event loop so each pytest
    test can create/tear down independently (Motor collections are loop-bound).
    We ALSO override `services.db` for the duration of the call so
    _recompute_contract_status reads from the same client.
    """
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    _db = client[os.environ["DB_NAME"]]

    import services as _services
    original_db = _services.db
    _services.db = _db
    try:
        cid = new_id()
        marker = uuid.uuid4().hex[:6]
        await _db.contracts.insert_one({
            "id": cid,
            "contract_number": f"CT-B-{marker}",
            "client_id": "test-client",
            "item_id": "test-item",
            "item_type": "car",
            "loan_amount": loan,
            "interest_rate": rate,
            "contract_date": contract_date_iso,
            "due_date": due_date_iso,
            "status": "active",
            "created_at": utcnow_iso(),
        })
        for p in payments:
            await _db.payments.insert_one({
                "id": new_id(),
                "contract_id": cid,
                "amount": p["amount"],
                "type": p["type"],
                "date": p["date"],
                "receipt_number": f"RC-B-{marker}-{p['date']}",
                "created_at": utcnow_iso(),
            })
        doc = await _db.contracts.find_one({"id": cid}, {"_id": 0})
        recomputed = await _recompute_contract_status(doc)
        await _db.payments.delete_many({"contract_id": cid})
        await _db.contracts.delete_one({"id": cid})
        return recomputed
    finally:
        _services.db = original_db
        client.close()


def _seed(loan, rate, contract_date_iso, due_date_iso, payments):
    return asyncio.run(_seed_and_recompute(loan, rate, contract_date_iso, due_date_iso, payments))


class TestRuleBHybridInterest:
    def test_no_partial_matches_rule_a(self):
        c = _seed(
            loan=500, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso=date.today().isoformat(),
            payments=[],
        )
        expected = round(50 * c["months_elapsed"], 2)
        assert c["interest_amount"] == expected, c

    def test_partial_before_month_2_reduces_month_2(self):
        c = _seed(
            loan=500, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 200, "type": "partial", "date": "2026-01-20"}],
        )
        billed = c["per_month_billed"]
        assert billed[0] == 50.0, f"month 1 must be $50 (Rule B anchor), got {billed[0]}"
        for m, val in enumerate(billed[1:], start=2):
            assert val == 30.0, f"month {m} expected $30 with partial before month 2, got {val}"

    def test_partial_after_month_2_anchor_does_not_reduce_month_2(self):
        c = _seed(
            loan=500, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 200, "type": "partial", "date": "2026-02-20"}],
        )
        billed = c["per_month_billed"]
        assert billed[0] == 50.0
        if len(billed) >= 2:
            assert billed[1] == 50.0, f"month 2 must still be $50 (partial arrived AFTER Feb 11), got {billed[1]}"
        if len(billed) >= 3:
            assert billed[2] == 30.0, f"month 3 must be $30 (principal reduced), got {billed[2]}"

    def test_per_month_interest_shows_current_month_rate(self):
        c = _seed(
            loan=500, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 200, "type": "partial", "date": "2026-01-20"}],
        )
        billed = c["per_month_billed"]
        assert c["per_month_interest"] == billed[-1]

    def test_per_month_interest_next_predicts_next_month(self):
        c = _seed(
            loan=500, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 200, "type": "partial", "date": "2026-01-20"}],
        )
        assert c["per_month_interest_next"] == 30.0, c

    def test_multiple_partials_stack(self):
        c = _seed(
            loan=500, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[
                {"amount": 200, "type": "partial", "date": "2026-01-20"},
                {"amount": 100, "type": "partial", "date": "2026-02-15"},
            ],
        )
        billed = c["per_month_billed"]
        assert billed[0] == 50.0
        if len(billed) >= 2:
            assert billed[1] == 30.0
        if len(billed) >= 3:
            assert billed[2] == 20.0
