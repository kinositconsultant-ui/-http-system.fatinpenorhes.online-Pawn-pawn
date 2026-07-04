"""Iter20 backend regression: monthly interest (Article 4) + Next Payment block in receipt PDF.

Scope:
  * Verify GET /api/contracts response includes months_elapsed, per_month_interest, next_interest_date.
  * Verify interest math (loan × rate/100) × months_elapsed on multiple contracts.
  * Verify next_interest_date is strictly in the future and (next - contract_date).days % 30 == 0.
  * Verify PDF: repayment receipt has "Interest Rate (per month)", "Months Billed So Far",
    "Pagamentu Tuir Mai · Next Payment" block, bilingual advisory.
  * Verify PDF: disbursement receipt does NOT include "Next Payment" block.
  * Verify PDF: fully-paid contract receipt does NOT include "Next Payment" block.
  * Regression: penalty_full = loan × 0.10 for overdue; _recompute idempotent.
  * Regression: pawn item block + signature line present on same PDF.
"""

import os
import io
import math
from datetime import date, datetime

import pytest
import requests
import pypdf


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pawnly-pro.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def contracts(session):
    r = session.get(f"{BASE_URL}/api/contracts", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and len(data) > 0, "no contracts returned"
    return data


# ---------- New fields present on every contract ----------

class TestContractNewFields:
    def test_all_contracts_expose_new_fields(self, contracts):
        missing_fields = []
        for c in contracts:
            for field in ("months_elapsed", "per_month_interest", "next_interest_date"):
                if field not in c:
                    missing_fields.append((c.get("contract_number"), field))
                    break
        assert not missing_fields, f"contracts missing new fields: {missing_fields[:5]}"

    def test_months_elapsed_is_positive_int(self, contracts):
        bad = [(c.get("contract_number"), c.get("months_elapsed"))
               for c in contracts
               if not isinstance(c.get("months_elapsed"), int) or c["months_elapsed"] < 1]
        assert not bad, f"months_elapsed invalid on: {bad[:5]}"

    def test_per_month_interest_matches_loan_times_rate(self, contracts):
        # per_month_interest == round(loan * rate / 100, 2)
        mismatches = []
        for c in contracts:
            expected = round(float(c["loan_amount"]) * float(c["interest_rate"]) / 100.0, 2)
            if abs(float(c["per_month_interest"]) - expected) > 0.01:
                mismatches.append((c.get("contract_number"), c["per_month_interest"], expected))
        assert not mismatches, f"per_month_interest mismatches: {mismatches[:5]}"

    def test_interest_amount_equals_per_month_times_months(self, contracts):
        mismatches = []
        for c in contracts:
            expected = round(float(c["per_month_interest"]) * int(c["months_elapsed"]), 2)
            if abs(float(c["interest_amount"]) - expected) > 0.01:
                mismatches.append((c.get("contract_number"),
                                   c["interest_amount"], expected,
                                   c["per_month_interest"], c["months_elapsed"]))
        assert not mismatches, f"interest_amount != per_month*months on: {mismatches[:5]}"


# ---------- Article 4 rule: months_elapsed = max(1, ceil(days/30)) ----------

class TestArticle4MonthsElapsed:
    def _compute_expected_months(self, contract_date_iso: str, due_date_iso: str) -> int:
        cs = date.fromisoformat(contract_date_iso)
        du = date.fromisoformat(due_date_iso)
        eff = max(du, date.today())
        days = max(0, (eff - cs).days)
        return max(1, math.ceil(days / 30)) if days > 0 else 1

    def test_fresh_contract_months_is_one(self, contracts):
        # A contract with days_elapsed < 30 -> months = 1
        fresh = [c for c in contracts
                 if self._compute_expected_months(c["contract_date"], c["due_date"]) == 1]
        assert len(fresh) > 0, "expected at least one fresh contract in dataset"
        bad = [(c.get("contract_number"), c["months_elapsed"]) for c in fresh if c["months_elapsed"] != 1]
        assert not bad, f"fresh contracts must have months_elapsed=1, got: {bad[:5]}"

    def test_all_contracts_match_article4_formula(self, contracts):
        wrong = []
        for c in contracts:
            expected = self._compute_expected_months(c["contract_date"], c["due_date"])
            if int(c["months_elapsed"]) != expected:
                wrong.append((c.get("contract_number"),
                              c["contract_date"], c["due_date"],
                              c["months_elapsed"], expected))
        assert not wrong, f"months_elapsed formula mismatches: {wrong[:5]}"

    def test_ctr_2026_0115_matches_expected_31_months(self, contracts):
        # Main agent's canary: CTR-2026-0115, loan $500, rate 15%, contract 2024-01-01
        c = next((x for x in contracts if x.get("contract_number") == "CTR-2026-0115"), None)
        if c is None:
            pytest.skip("CTR-2026-0115 not present")
        assert c["months_elapsed"] == 31, f"expected 31, got {c['months_elapsed']}"
        assert abs(float(c["per_month_interest"]) - 75.0) < 0.01
        assert abs(float(c["interest_amount"]) - 2325.0) < 0.01


# ---------- next_interest_date is strictly future and month-aligned ----------

class TestNextInterestDate:
    def test_next_date_strictly_future(self, contracts):
        today = date.today()
        bad = []
        for c in contracts:
            n = date.fromisoformat(c["next_interest_date"])
            if n <= today:
                bad.append((c.get("contract_number"), c["next_interest_date"]))
        assert not bad, f"next_interest_date not in future for: {bad[:5]}"

    def test_next_date_multiple_of_30_from_contract_start(self, contracts):
        bad = []
        for c in contracts:
            cs = date.fromisoformat(c["contract_date"])
            n = date.fromisoformat(c["next_interest_date"])
            diff = (n - cs).days
            if diff <= 0 or diff % 30 != 0:
                bad.append((c.get("contract_number"), c["contract_date"], c["next_interest_date"], diff))
        assert not bad, f"next_interest_date not on 30-day boundary: {bad[:5]}"


# ---------- Idempotency + penalty regression ----------

class TestIdempotencyAndPenalty:
    def test_recompute_is_idempotent_via_repeated_get(self, session, contracts):
        # Pick an overdue contract, GET twice, values must be identical.
        overdue = next((c for c in contracts
                        if c.get("status") in ("overdue", "auction_ready")), None)
        if overdue is None:
            pytest.skip("no overdue contract available")
        r1 = session.get(f"{BASE_URL}/api/contracts/{overdue['id']}", timeout=15)
        r2 = session.get(f"{BASE_URL}/api/contracts/{overdue['id']}", timeout=15)
        assert r1.status_code == 200 and r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        for k in ("months_elapsed", "per_month_interest", "interest_amount",
                  "next_interest_date", "penalty_full", "total_due"):
            assert d1[k] == d2[k], f"non-idempotent for {k}: {d1[k]} vs {d2[k]}"

    def test_penalty_full_is_loan_times_ten_percent_on_overdue(self, contracts):
        overdue = [c for c in contracts if c.get("status") in ("overdue", "auction_ready")]
        assert overdue, "no overdue contracts in dataset"
        wrong = []
        for c in overdue:
            expected = round(float(c["loan_amount"]) * 0.10, 2)
            if abs(float(c.get("penalty_full", 0)) - expected) > 0.01:
                wrong.append((c["contract_number"], c.get("penalty_full"), expected))
        assert not wrong, f"penalty_full != 10% loan for overdue: {wrong[:5]}"


# ---------- PDF verification ----------

def _fetch_pdf_text(session, url: str) -> str:
    r = session.get(url, timeout=25)
    assert r.status_code == 200, f"PDF fetch failed {r.status_code}: {url}"
    assert r.headers.get("content-type", "").startswith("application/pdf"), \
        f"not a PDF: {r.headers}"
    reader = pypdf.PdfReader(io.BytesIO(r.content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


class TestReceiptPDFNextPaymentBlock:
    """Payment PDFs — verify Next Payment block presence/absence rules."""

    def _list_payments(self, session, contract_id: str):
        r = session.get(f"{BASE_URL}/api/payments", params={"contract_id": contract_id}, timeout=15)
        assert r.status_code == 200, r.text
        return r.json()

    def test_repayment_pdf_contains_next_payment_block(self, session, contracts):
        # Find an active or overdue contract that has a non-disbursement payment
        target = None
        target_payment = None
        for c in contracts:
            if float(c.get("remaining_balance", 0)) <= 0.01:
                continue
            pays = self._list_payments(session, c["id"])
            non_disb = [p for p in pays if p.get("type") != "disbursement"]
            if non_disb:
                target = c
                target_payment = non_disb[0]
                break
        if not target:
            pytest.skip("no contract with non-disbursement payment available")

        text = _fetch_pdf_text(session, f"{BASE_URL}/api/payments/{target_payment['id']}/pdf")

        # Interest rate / months labels
        assert "Interest Rate (per month)" in text, "missing 'Interest Rate (per month)' label"
        assert "Months Billed So Far" in text, "missing 'Months Billed So Far' label"

        # Next Payment section
        assert "Next Payment" in text, "missing 'Next Payment' header"
        # Tetum header is on same line block
        assert "Pagamentu Tuir Mai" in text, "missing Tetum 'Pagamentu Tuir Mai' header"

        # Row labels
        for label in ("Next payment date", "Current balance",
                      "Next month interest", "If unpaid by that date"):
            assert label in text, f"missing row label: {label!r}"

        # Bilingual advisory paragraph
        assert "Please pay by" in text, "missing English advisory 'Please pay by'"
        assert "Favor selu iha loron" in text, "missing Tetum advisory 'Favor selu iha loron'"

        # next_interest_date should appear as a literal string in the PDF
        nd = target["next_interest_date"]
        # tolerate PDF text wrapping (yyyy-mm-dd may split with spaces on extraction)
        assert nd in text or nd.replace("-", "") in text.replace("-", ""), \
            f"expected next_interest_date {nd} in PDF text"

    def test_disbursement_pdf_omits_next_payment_block(self, session, contracts):
        # Every contract auto-creates a disbursement receipt on creation.
        target = None
        target_disb = None
        for c in contracts:
            pays = self._list_payments(session, c["id"])
            disb = next((p for p in pays if p.get("type") == "disbursement"), None)
            if disb:
                target = c
                target_disb = disb
                break
        assert target and target_disb, "no disbursement payment available"

        text = _fetch_pdf_text(session, f"{BASE_URL}/api/payments/{target_disb['id']}/pdf")
        # The disbursement receipt uses "Interest Rate (applies at maturity)" — NOT the monthly label
        assert "Interest Rate (applies at maturity)" in text, "disbursement missing maturity label"
        # Must NOT contain the Next Payment block
        assert "Pagamentu Tuir Mai" not in text, "disbursement PDF unexpectedly shows Next Payment block"
        assert "Next month interest" not in text, "disbursement PDF unexpectedly shows 'Next month interest' row"

    def test_fully_paid_receipt_omits_next_payment_block(self, session, contracts):
        # Find a redeemed contract with a non-disbursement payment
        target = None
        target_payment = None
        for c in contracts:
            if c.get("status") != "redeemed":
                continue
            pays = self._list_payments(session, c["id"])
            non_disb = [p for p in pays if p.get("type") != "disbursement"]
            if non_disb:
                target = c
                target_payment = non_disb[-1]  # most recent
                break
        if not target:
            pytest.skip("no redeemed contract with repayment found")

        text = _fetch_pdf_text(session, f"{BASE_URL}/api/payments/{target_payment['id']}/pdf")
        # remaining <= 0.01 → block skipped
        assert "Pagamentu Tuir Mai" not in text, \
            "fully-paid receipt unexpectedly shows Next Payment block"
        assert "Next month interest" not in text, \
            "fully-paid receipt unexpectedly shows 'Next month interest' row"


class TestRegressionPawnItemAndSignature:
    """Iter18 regression — pawn item block + client name printed on signature line."""

    def test_receipt_pdf_has_item_and_signature(self, session, contracts):
        # Prefer disbursement receipt (guaranteed present with item block).
        target_payment = None
        target_client = None
        for c in contracts:
            r = session.get(f"{BASE_URL}/api/payments", params={"contract_id": c["id"]}, timeout=15)
            if r.status_code != 200:
                continue
            pays = r.json()
            disb = next((p for p in pays if p.get("type") == "disbursement"), None)
            if disb:
                target_payment = disb
                target_client = c.get("client_id")
                # Fetch client for name
                cr = session.get(f"{BASE_URL}/api/clients/{target_client}", timeout=15)
                if cr.status_code == 200:
                    target_client = cr.json()
                break
        assert target_payment, "no disbursement payment found"

        text = _fetch_pdf_text(session, f"{BASE_URL}/api/payments/{target_payment['id']}/pdf")

        # Pawn item block markers used since iter18
        # (block header "Pawn Item" is the anchor)
        assert ("Pawn Item" in text) or ("Sasan" in text), \
            "iter18 pawn item block appears missing from receipt PDF"

        # Signature line: client name should be printed on the signature area.
        if isinstance(target_client, dict) and target_client.get("name"):
            name = target_client["name"]
            assert name in text, f"client name {name!r} missing on signature area"
