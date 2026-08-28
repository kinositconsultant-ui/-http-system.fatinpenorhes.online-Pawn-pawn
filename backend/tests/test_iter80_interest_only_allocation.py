"""iter80 — Interest-only payments must NEVER reduce principal.

Client spec (Jun 2026):
  Original Loan $3,000 · Interest due $300 · interest_only payment $300
  → Interest Paid $300, Principal Paid $0, Principal Left $3,000 (unchanged).

Also verifies per-payment allocation splits are persisted onto payment docs
(principal_paid / interest_paid / penalty_paid) for the Payment History PDF.
"""
from __future__ import annotations

import asyncio
import os
import uuid

from motor.motor_asyncio import AsyncIOMotorClient

from deps import new_id, utcnow_iso
from services import _recompute_contract_status


async def _seed_full(loan, rate, contract_date_iso, due_date_iso, payments, interest_rule="M1"):
    """Seed contract + payments, recompute, return (contract, payment_docs)."""
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
            "contract_number": f"CT-I80-{marker}",
            "client_id": "test-client",
            "item_id": "test-item",
            "item_type": "car",
            "loan_amount": loan,
            "interest_rate": rate,
            "contract_date": contract_date_iso,
            "due_date": due_date_iso,
            "status": "active",
            "interest_rule": interest_rule,
            "created_at": utcnow_iso(),
        })
        for p in payments:
            await _db.payments.insert_one({
                "id": new_id(),
                "contract_id": cid,
                "amount": p["amount"],
                "type": p["type"],
                "date": p["date"],
                "receipt_number": f"RC-I80-{marker}-{p['date']}",
                "created_at": utcnow_iso(),
            })
        doc = await _db.contracts.find_one({"id": cid}, {"_id": 0})
        recomputed = await _recompute_contract_status(doc)
        pmt_docs = await _db.payments.find({"contract_id": cid}, {"_id": 0}).to_list(100)
        await _db.payments.delete_many({"contract_id": cid})
        await _db.contracts.delete_one({"id": cid})
        return recomputed, pmt_docs
    finally:
        _services.db = original_db
        client.close()


def _seed(**kw):
    return asyncio.run(_seed_full(**kw))


class TestInterestOnlyNeverTouchesPrincipal:
    def test_client_exact_example(self):
        """$3,000 @ 10%, interest_only $300 → principal untouched."""
        c, pmts = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 300, "type": "interest_only", "date": "2026-01-20"}],
        )
        assert c["loan_amount"] == 3000
        assert c["original_loan_amount"] == 3000.0
        assert c["principal_paid"] == 0.0
        assert c["principal_remaining"] == 3000.0
        assert c["current_principal"] == 3000.0
        assert c["interest_paid"] == 300.0
        p = pmts[0]
        assert p["principal_paid"] == 0.0
        assert p["interest_paid"] == 300.0
        assert p["penalty_paid"] == 0.0

    def test_overpaid_interest_only_still_never_reduces_principal(self):
        """interest_only $500 when only $300 owed → NO spillover into principal."""
        c, pmts = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 500, "type": "interest_only", "date": "2026-01-20"}],
        )
        assert c["principal_paid"] == 0.0
        assert c["principal_remaining"] == 3000.0
        assert pmts[0]["principal_paid"] == 0.0
        assert pmts[0]["interest_paid"] == 500.0

    def test_interest_only_under_m2_rule(self):
        c, _ = _seed(
            loan=1000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 100, "type": "interest_only", "date": "2026-01-15"}],
            interest_rule="M2",
        )
        assert c["principal_paid"] == 0.0
        assert c["principal_remaining"] == 1000.0
        assert c["interest_paid"] == 100.0

    def test_partial_m1_allocation_persisted(self):
        """Regression: partial keeps interest-first split, and split is stored on payment."""
        c, pmts = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 1000, "type": "partial", "date": "2026-01-20"}],
        )
        assert c["interest_paid"] == 300.0
        assert c["principal_paid"] == 700.0
        assert c["principal_remaining"] == 2300.0
        p = pmts[0]
        assert p["interest_paid"] == 300.0
        assert p["principal_paid"] == 700.0

    def test_interest_only_then_partial_sequence(self):
        """interest_only clears interest; later partial goes fully to principal."""
        c, pmts = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[
                {"amount": 300, "type": "interest_only", "date": "2026-01-15"},
                {"amount": 1000, "type": "partial", "date": "2026-01-20"},
            ],
        )
        assert c["interest_paid"] >= 300.0
        assert c["principal_paid"] == 1000.0
        assert c["principal_remaining"] == 2000.0
        by_type = {p["type"]: p for p in pmts}
        assert by_type["interest_only"]["principal_paid"] == 0.0
        assert by_type["partial"]["principal_paid"] == 1000.0
