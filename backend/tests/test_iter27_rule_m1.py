"""Iteration 27 — Rule M1 (Method 1 payment allocation for new contracts).

M1 rule (business owner decision, Feb 2026):
- Month 1 interest = 10% × original loan (fixed anchor)
- Month N (N>1) interest = 10% × principal remaining at Month N anchor date
  (declining balance — same as Rule B)
- Partial payment allocation: INTEREST FIRST, then principal (Method 1)
- NO compounding on pure delinquency (if client pays nothing, next month's
  interest is still 10% × principal, not 10% × (principal + unpaid interest))

Business owner examples ($3,000 loan @ 10%):
  Ex 1: Partial $1,000 paid Jan 20:
    - $300 → M1 interest cleared
    - $700 → principal → remaining = $2,300
    - Month 2 interest = 10% × $2,300 = $230  ✓
  Ex 2: Interest-only $300 paid Jan 20:
    - $300 → M1 interest cleared
    - Principal unchanged at $3,000
    - Month 2 interest = 10% × $3,000 = $300  ✓
  Ex 3: No payment at all:
    - Month 2 interest = 10% × $3,000 = $300 (NOT $330 — no compound)  ✓
"""
from __future__ import annotations

from tests.test_iter26_rule_b_hybrid import _seed


class TestRuleM1PaymentAllocation:
    def test_example_1_partial_1000(self):
        """Business owner's Example 1: $3000 @ 10%, $1000 partial → $230 next month."""
        c = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 1000, "type": "partial", "date": "2026-01-20"}],
            interest_rule="M1",
        )
        assert c["interest_rule"] == "M1"
        assert c["interest_paid"] == 300.0, f"interest_paid should be $300 (M1 clears M1 int first), got {c['interest_paid']}"
        assert c["principal_paid"] == 700.0, f"principal_paid should be $700 (remainder after int), got {c['principal_paid']}"
        assert c["principal_remaining"] == 2300.0
        # Month 1 anchor uses $3000, Months 2+ use $2300
        billed = c["per_month_billed"]
        assert billed[0] == 300.0, f"month 1 = $300, got {billed[0]}"
        for m, val in enumerate(billed[1:], start=2):
            assert val == 230.0, f"month {m} expected $230, got {val}"
        assert c["per_month_interest_next"] == 230.0

    def test_example_2_interest_only_300(self):
        """Business owner's Example 2: $3000 @ 10%, $300 interest-only → $300 next month."""
        c = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 300, "type": "interest_only", "date": "2026-01-20"}],
            interest_rule="M1",
        )
        assert c["interest_paid"] == 300.0
        assert c["principal_paid"] == 0.0
        assert c["principal_remaining"] == 3000.0
        billed = c["per_month_billed"]
        # All months = $300 because principal never drops
        for m, val in enumerate(billed, start=1):
            assert val == 300.0, f"month {m} expected $300, got {val}"
        assert c["per_month_interest_next"] == 300.0

    def test_no_compounding_on_delinquency(self):
        """Client pays nothing → next month is 10% × PRINCIPAL, NOT 10% × (principal + unpaid interest)."""
        c = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[],
            interest_rule="M1",
        )
        # If we were compounding, month 2 would be 10% × ($3000+$300) = $330.
        # Under M1 with no-compound rule: all months = $300.
        billed = c["per_month_billed"]
        for m, val in enumerate(billed, start=1):
            assert val == 300.0, f"month {m}: expected $300 (no-compound), got {val}"
        assert c["per_month_interest_next"] == 300.0

    def test_legacy_m2_rule_unchanged(self):
        """Old contracts (no interest_rule set) should default to M2 and give the OLD behaviour."""
        # We explicitly pass interest_rule=None-ish via an empty field... but the seed helper
        # always sets it. So we simulate by passing "M2".
        c = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[{"amount": 1000, "type": "partial", "date": "2026-01-20"}],
            interest_rule="M2",
        )
        # M2: partial goes fully to principal → principal_paid=$1000, remaining=$2000
        assert c["principal_paid"] == 1000.0, f"M2 sends all to principal, got {c['principal_paid']}"
        assert c["interest_paid"] == 0.0
        assert c["principal_remaining"] == 2000.0
        # Month 2+ = 10% × $2000 = $200 (NOT $230)
        billed = c["per_month_billed"]
        assert billed[0] == 300.0
        if len(billed) >= 2:
            assert billed[1] == 200.0, f"M2 month 2 = $200, got {billed[1]}"

    def test_two_partials_stack_correctly_under_m1(self):
        """Multiple partials — each allocated interest-first at its date."""
        c = _seed(
            loan=3000, rate=10,
            contract_date_iso="2026-01-10",
            due_date_iso="2026-02-10",
            payments=[
                {"amount": 500, "type": "partial", "date": "2026-01-20"},   # $300 int + $200 princ
                {"amount": 500, "type": "partial", "date": "2026-02-20"},   # $230 int (M2) + $270 princ
            ],
            interest_rule="M1",
        )
        # Month 1: $300 interest on $3000
        # After Jan 20 partial: interest_paid=$300, principal_paid=$200, principal=$2800
        # Month 2 anchor (Feb 10): interest owed = 10% × $2800 = $280
        # Feb 20 partial: interest owed at that point = $280 (unpaid),
        #   $500 covers all $280 → interest_paid=$580, remainder $220 → principal
        #   principal_paid = $200 + $220 = $420, principal = $2580
        # Month 3 anchor (Mar 10): interest owed = 10% × $2580 = $258
        billed = c["per_month_billed"]
        assert billed[0] == 300.0
        if len(billed) >= 2:
            assert billed[1] == 280.0, f"month 2 = $280 (10% × $2800 after Jan partial), got {billed[1]}"
        if len(billed) >= 3:
            assert billed[2] == 258.0, f"month 3 = $258 (10% × $2580 after Feb partial), got {billed[2]}"
