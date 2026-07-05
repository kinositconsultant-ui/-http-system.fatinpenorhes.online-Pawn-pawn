"""Iteration 22 (business change) — Rule A: Strict calendar month + 1 grace day.

Unit tests for `_months_billed`. This is the interest-billing helper that
replaced the older `ceil(days / 30)` logic per Article 4 of Fatin Penhores'
business rules.

Rule:
  - The first monthly billing period is ALWAYS charged (min 1).
  - Payment on the monthly anniversary of the start date → same month billed.
  - Payment 1 day AFTER the anniversary → new full month begins.

If any of these tests fail, the client-facing money math is wrong. Fix before
merging.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Allow the tests to import server.py from /app/backend without a package
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Bootstrap the required env before importing server (which reads .env at import)
import os
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

from server import _months_billed  # noqa: E402


class TestMonthsBilledRuleA:
    def test_same_day(self):
        assert _months_billed(date(2026, 7, 10), date(2026, 7, 10)) == 1

    def test_within_first_month(self):
        # July 10 → July 15 (5 days) → still month 1
        assert _months_billed(date(2026, 7, 10), date(2026, 7, 15)) == 1
        # July 10 → July 31 (21 days) → still month 1
        assert _months_billed(date(2026, 7, 10), date(2026, 7, 31)) == 1
        # July 10 → Aug 9 (30 days, one day short of anniversary) → still 1
        assert _months_billed(date(2026, 7, 10), date(2026, 8, 9)) == 1

    def test_anniversary_is_still_same_month(self):
        # July 10 → Aug 10 (exactly 1 month) → 1
        assert _months_billed(date(2026, 7, 10), date(2026, 8, 10)) == 1

    def test_one_day_past_anniversary(self):
        # July 10 → Aug 11 → 2 (new month kicks in)
        assert _months_billed(date(2026, 7, 10), date(2026, 8, 11)) == 2

    def test_two_month_anniversary(self):
        # July 10 → Sep 10 → 2 (2nd anniversary is not yet a new month)
        assert _months_billed(date(2026, 7, 10), date(2026, 9, 10)) == 2

    def test_three_months_after_grace(self):
        # July 10 → Sep 11 → 3 (one day past 2nd anniversary)
        assert _months_billed(date(2026, 7, 10), date(2026, 9, 11)) == 3

    def test_early_month_first_day(self):
        # Start on the 1st → paid on the 15th → still 1 (within first month)
        assert _months_billed(date(2026, 7, 1), date(2026, 7, 15)) == 1

    def test_end_of_month_start_31st_no_31st_in_next_month(self):
        # Start July 31 (dateutil.relativedelta caps to the last valid day of the next month)
        # Aug 31 is valid → same month
        assert _months_billed(date(2026, 7, 31), date(2026, 8, 31)) == 1
        # Sep 1 is one day past Aug 31 anniversary → new month
        assert _months_billed(date(2026, 7, 31), date(2026, 9, 1)) == 2

    def test_leap_year_boundary(self):
        # Start Feb 29 2028 (leap). Each monthly anniversary is capped to the
        # last valid day of the target month. Feb 28 2029 is the 12th
        # anniversary — still same billing month (12); Mar 1 2029 = 13.
        assert _months_billed(date(2028, 2, 29), date(2029, 2, 28)) == 12
        assert _months_billed(date(2028, 2, 29), date(2029, 3, 1)) == 13

    def test_payment_before_start_returns_one(self):
        # Nonsensical but should not crash; must return 1
        assert _months_billed(date(2026, 7, 10), date(2026, 7, 1)) == 1

    def test_scenarios_from_business_owner(self):
        """Direct scenarios from the user brief:
        - 10 July → 10 August = 1 month
        - 10 July → 11 August = 2 months
        - 1 July → 15 July = 1 month
        - 20 July → 20 August = 1 month (30 days)
        - 20 July → 21 August = 2 months
        """
        assert _months_billed(date(2026, 7, 10), date(2026, 8, 10)) == 1
        assert _months_billed(date(2026, 7, 10), date(2026, 8, 11)) == 2
        assert _months_billed(date(2026, 7, 1), date(2026, 7, 15)) == 1
        assert _months_billed(date(2026, 7, 20), date(2026, 8, 20)) == 1
        assert _months_billed(date(2026, 7, 20), date(2026, 8, 21)) == 2

    def test_long_running_contract(self):
        # 1 year 2 months and 3 days later: 14 full months
        # start Jul 10 2026 → paid Sep 13 2027
        # anniv 1 = Aug 10 2026
        # anniv 12 = Jul 10 2027
        # anniv 13 = Aug 10 2027 (< Sep 13 → +1 more)
        # anniv 14 = Sep 10 2027 (< Sep 13 → +1 more)
        # anniv 15 = Oct 10 2027 (> Sep 13 → stop)
        assert _months_billed(date(2026, 7, 10), date(2027, 9, 13)) == 15
