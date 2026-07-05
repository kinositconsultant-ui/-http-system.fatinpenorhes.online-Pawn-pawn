"""Iteration 23 — WhatsApp reminder body now includes the interest math (Rule A).

Unit tests for the message template so we don't accidentally regress the
client-facing wording or the money math.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

from dateutil.relativedelta import relativedelta  # noqa: E402
from deps import months_billed  # noqa: E402
from reminders import _MSG_EN, _MSG_TET, _short_contract  # noqa: E402


def _render(tmpl: str, *, start: date, today: date, days: int,
            loan: float = 500.0, rate: float = 10.0, name: str = "João B.",
            contract_number: str = "CTR-2026-0042") -> str:
    per_month = round(loan * rate / 100.0, 2)
    months = months_billed(start, today)
    interest_total = round(per_month * months, 2)
    total_due = round(loan + interest_total, 2)
    next_month_date = (start + relativedelta(months=months) + timedelta(days=1)).isoformat()
    next_interest_total = round(interest_total + per_month, 2)
    return tmpl.format(
        name=name,
        contract_number=_short_contract(contract_number),
        days=days,
        days_left=max(0, 10 - days),
        loan=f"{loan:,.2f}",
        per_month=f"{per_month:,.2f}",
        months=months,
        interest_total=f"{interest_total:,.2f}",
        total_due=f"{total_due:,.2f}",
        next_month_date=next_month_date,
        next_interest_total=f"{next_interest_total:,.2f}",
    )


class TestReminderBody:
    def test_en_body_contains_math(self):
        body = _render(_MSG_EN, start=date(2026, 7, 10), today=date(2026, 8, 17), days=7)
        # 500 × 10% = 50/month. months_billed(Jul 10, Aug 17) = 2 (past Aug 11 anniv+1).
        assert "$500.00" in body
        assert "2×$50.00" in body
        assert "$600.00" in body  # total_due = loan + 2×interest = 600
        # Next month kicks in Sep 11, interest goes 2→3 months = $150
        assert "$150.00" in body
        assert "2026-09-11" in body
        assert "days overdue" in body
        assert "WhatsApp" in body

    def test_tet_body_contains_math_and_language(self):
        body = _render(_MSG_TET, start=date(2026, 7, 10), today=date(2026, 8, 17), days=7)
        # Tetum-specific words present
        assert "Ola" in body
        assert "atrazu" in body
        assert "juru" in body
        assert "leilão" in body
        # Same numbers
        assert "$500.00" in body
        assert "2×$50.00" in body

    def test_body_within_whatsapp_limit(self):
        # WhatsApp free-form message limit ~1024 chars — must stay well under
        body_en = _render(_MSG_EN, start=date(2026, 7, 10), today=date(2026, 8, 17), days=7,
                          name="A very long client name Da Silva Soares",
                          contract_number="CTR-2026-9999")
        body_tet = _render(_MSG_TET, start=date(2026, 7, 10), today=date(2026, 8, 17), days=7,
                           name="A very long client name Da Silva Soares",
                           contract_number="CTR-2026-9999")
        assert len(body_en) < 500, f"EN body too long: {len(body_en)}"
        assert len(body_tet) < 500, f"TET body too long: {len(body_tet)}"

    def test_short_contract_helper(self):
        assert _short_contract("CTR-2026-0042") == "CT-2026-42"
        assert _short_contract(None) == ""
        # Malformed — return as-is
        assert _short_contract("weird") == "weird"

    def test_scenario_from_business_owner(self):
        """Direct scenario the user gave: 'Bo'o kontratu iha loron 10 Jul.
        Ohin loron 5 Ago, ó tenke selu $500 + $50 juru = $550. Iha loron
        11 Ago juru sae ba $100.'"""
        body = _render(_MSG_EN, start=date(2026, 7, 10), today=date(2026, 8, 5), days=7)
        assert "$500.00 + 1×$50.00" in body
        assert "$550.00" in body     # total_due
        assert "2026-08-11" in body  # next month kicks in
        assert "$100.00" in body     # interest doubles to $100
