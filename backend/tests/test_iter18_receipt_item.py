"""Iter18 backend tests — Payment Receipt PDF: Pawn Item block + client name on signature line.

Covers:
- Disbursement PDF: Pawn Item block + client name printed on signature line
- Regular repayment PDF: same block + still shows repayment box
- Orphan-safe: item deleted → PDF still 200, no Pawn Item block
- Free-text description round-trip (Deskrisaun: ...)
- Regressions: iter16 (disbursement title/box), iter17 (reminders status/run), iter10 (name+machine_number)
"""
import io
import os
from datetime import date, timedelta

import pytest
import requests
from pypdf import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pawnly-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASSWORD = "admin123"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "".join((p.extract_text() or "") for p in reader.pages)


@pytest.fixture(scope="module")
def car_client_contract(admin_session):
    """Create a car + client + contract with a rich description so we can verify all fields."""
    client_r = admin_session.post(f"{API}/clients", json={
        "full_name": "TEST_Iter18 Auction Client",
        "id_type": "Passport",
        "id_number": f"P-ITER18-{date.today().isoformat()}",
        "phone": "+670 8800 1818",
        "municipality": "Dili",
    })
    assert client_r.status_code == 200, client_r.text
    client = client_r.json()

    car_r = admin_session.post(f"{API}/items/car", json={
        "name": "TEST_Ford Ranger Wildtrak",
        "brand": "Ford",
        "model": "Ranger",
        "description": "Test description 2026",
        "plate": "TL-ITER18-A",
        "machine_number": "ENG-ITER18-XX",
        "chassis": "CHS-ITER18-YY",
        "color": "Blue",
        "manufacture_year": 2021,
        "market_value": 15000.0,
        "location": "warehouse",
    })
    assert car_r.status_code == 200, car_r.text
    car = car_r.json()

    today = date.today()
    ct = admin_session.post(f"{API}/contracts", json={
        "client_id": client["id"],
        "item_id": car["id"],
        "item_type": "car",
        "loan_amount": 2000.0,
        "interest_rate": 10,
        "contract_date": today.isoformat(),
        "due_date": (today + timedelta(days=30)).isoformat(),
    })
    assert ct.status_code == 200, ct.text
    contract = ct.json()

    yield {"client": client, "item": car, "contract": contract}

    # cleanup
    admin_session.delete(f"{API}/contracts/{contract['id']}")
    admin_session.delete(f"{API}/items/car/{car['id']}")
    admin_session.delete(f"{API}/clients/{client['id']}")


# ---------- Feature 1: Disbursement receipt with Pawn Item block ----------
class TestDisbursementReceiptPawnItem:
    def _get_disbursement(self, admin_session, contract_id):
        r = admin_session.get(f"{API}/payments", params={"contract_id": contract_id})
        assert r.status_code == 200, r.text
        disbs = [p for p in r.json() if p.get("type") == "disbursement"]
        assert len(disbs) == 1, f"Expected 1 disbursement, got {len(disbs)}"
        return disbs[0]

    def test_disbursement_pdf_pawn_item_block(self, admin_session, car_client_contract):
        disb = self._get_disbursement(admin_session, car_client_contract["contract"]["id"])
        r = admin_session.get(f"{API}/payments/{disb['id']}/pdf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"

        text = _extract_pdf_text(r.content)
        # Pawn Item header appears
        assert "Pawn Item" in text, f"Missing 'Pawn Item' header. Text start: {text[:600]}"
        # All 4 labels from spec
        for lbl in ["Machine No.", "Chassis", "Plate", "Market Value"]:
            assert lbl in text, f"Missing label '{lbl}' in disbursement PDF"
        # Brand or item name appears
        assert ("Ford" in text) or ("Ranger" in text) or ("TEST_Ford" in text), \
            f"Item name/brand not found in Pawn Item block. Text: {text[:800]}"

    def test_disbursement_pdf_signature_names(self, admin_session, car_client_contract):
        disb = self._get_disbursement(admin_session, car_client_contract["contract"]["id"])
        r = admin_session.get(f"{API}/payments/{disb['id']}/pdf")
        assert r.status_code == 200
        text = _extract_pdf_text(r.content)
        client_name = car_client_contract["client"]["full_name"]
        assert client_name in text, f"Client full_name '{client_name}' missing from PDF"
        assert "Fatin Penhores" in text, "Officer name 'Fatin Penhores' missing"
        assert "Client Signature" in text, "Label 'Client Signature' missing"
        assert "Authorized Officer" in text, "Label 'Authorized Officer' missing"

    def test_disbursement_pdf_has_description_freetext(self, admin_session, car_client_contract):
        disb = self._get_disbursement(admin_session, car_client_contract["contract"]["id"])
        r = admin_session.get(f"{API}/payments/{disb['id']}/pdf")
        text = _extract_pdf_text(r.content)
        # 'Deskrisaun:' label + user-typed text
        assert "Deskrisaun" in text, "'Deskrisaun' label missing"
        assert "Test description 2026" in text, "Free-text description missing from receipt"

    # ---- REGRESSION iter16: title and disbursement-focused box ----
    def test_iter16_regression_disbursement_title_and_box(self, admin_session, car_client_contract):
        disb = self._get_disbursement(admin_session, car_client_contract["contract"]["id"])
        r = admin_session.get(f"{API}/payments/{disb['id']}/pdf")
        text = _extract_pdf_text(r.content)
        assert ("Loan Disbursement Receipt" in text) or ("Resibu Entrega Empr" in text), \
            f"Disbursement title missing. Start: {text[:400]}"
        assert "Amount Received by Client" in text, "Disbursement box field missing"
        assert "Interest Rate" in text, "Interest Rate label missing"
        assert "Contract Start" in text or "Contract Due" in text, "Contract date fields missing"
        # Must NOT have repayment-only fields
        assert "Principal Remaining" not in text, "Repayment field leaked into disbursement PDF"
        assert "Total Remaining Balance" not in text, "Repayment 'Total Remaining Balance' leaked"


# ---------- Feature 2: Regular repayment PDF (Pawn Item + repayment box coexist) ----------
class TestRegularPaymentReceipt:
    def test_regular_payment_pdf_shows_item_block_and_repayment_box(
        self, admin_session, car_client_contract
    ):
        today = date.today()
        pay = admin_session.post(f"{API}/payments", json={
            "contract_id": car_client_contract["contract"]["id"],
            "amount": 100.0,
            "type": "partial",
            "date": today.isoformat(),
        })
        assert pay.status_code == 200, pay.text
        payment = pay.json().get("payment") or pay.json()
        try:
            r = admin_session.get(f"{API}/payments/{payment['id']}/pdf")
            assert r.status_code == 200
            text = _extract_pdf_text(r.content)

            # Pawn item block still present
            assert "Pawn Item" in text, "Pawn Item block missing on regular payment"
            for lbl in ["Machine No.", "Chassis", "Plate", "Market Value"]:
                assert lbl in text, f"Missing '{lbl}' on regular payment PDF"

            # Repayment box still present
            assert "Principal Remaining" in text, "Repayment field missing on regular payment"
            assert "Interest Remaining" in text, "Interest Remaining missing"
            assert "Total Remaining Balance" in text, "Total Remaining Balance missing"

            # Signature auto-name
            assert car_client_contract["client"]["full_name"] in text, "Client name missing on sig"
            assert "Fatin Penhores" in text, "Officer name missing on sig"
            assert "Client Signature" in text
            assert "Authorized Officer" in text

            # Free-text description
            assert "Test description 2026" in text, "Description missing on regular PDF"
        finally:
            # best-effort: cannot delete payments via API in most systems; leave for cleanup
            pass


# ---------- Feature 3: Orphan safety — item deleted, PDF still generates ----------
class TestOrphanItemReceipt:
    def test_pdf_ok_when_item_deleted(self, admin_session):
        # Create a fresh disposable client + electronic item + contract
        client = admin_session.post(f"{API}/clients", json={
            "full_name": "TEST_Iter18 Orphan Client",
            "id_type": "Passport",
            "id_number": f"P-ORPHAN18-{date.today().isoformat()}",
            "phone": "+670 8811 1818",
            "municipality": "Dili",
        }).json()
        item = admin_session.post(f"{API}/items/electronic", json={
            "category": "phone", "brand": "Samsung", "model": "A50",
            "serial": "SN-ORPH-18", "condition": "good",
        }).json()
        today = date.today()
        c = admin_session.post(f"{API}/contracts", json={
            "client_id": client["id"],
            "item_id": item["id"],
            "item_type": "electronic",
            "loan_amount": 300.0,
            "interest_rate": 15,
            "contract_date": today.isoformat(),
            "due_date": (today + timedelta(days=30)).isoformat(),
        }).json()

        try:
            # Grab the auto disbursement payment
            pays = admin_session.get(f"{API}/payments", params={"contract_id": c["id"]}).json()
            disb = [p for p in pays if p.get("type") == "disbursement"][0]

            # DELETE the underlying item
            del_r = admin_session.delete(f"{API}/items/electronic/{item['id']}")
            assert del_r.status_code in (200, 204), del_r.text

            # PDF should still succeed
            r = admin_session.get(f"{API}/payments/{disb['id']}/pdf")
            assert r.status_code == 200, f"Orphan PDF failed: {r.status_code} {r.text[:400]}"
            assert r.content[:4] == b"%PDF"
            text = _extract_pdf_text(r.content)

            # Pawn Item block should be OMITTED
            assert "Pawn Item" not in text, "Pawn Item block should be omitted when item deleted"
            # But signature/officer must still be there
            assert "Fatin Penhores" in text
            assert client["full_name"] in text
        finally:
            admin_session.delete(f"{API}/contracts/{c['id']}")
            # item already deleted
            admin_session.delete(f"{API}/clients/{client['id']}")


# ---------- REGRESSION iter17: reminders status + run ----------
class TestIter17RemindersRegression:
    def test_reminders_status_structure(self, admin_session):
        r = admin_session.get(f"{API}/reminders/status")
        assert r.status_code == 200, r.text
        body = r.json()
        # local_time should be "09:00 Timor (UTC+9)"
        assert "09:00" in str(body.get("local_time", "")), body
        assert "Timor" in str(body.get("local_time", "")), body

    def test_reminders_run_works(self, admin_session):
        r = admin_session.post(f"{API}/reminders/run")
        assert r.status_code == 200, r.text
        body = r.json()
        # Should include either scanned count or disabled flag
        assert ("scanned" in body) or ("disabled" in body), body


# ---------- REGRESSION iter10: name + machine_number round-trip ----------
class TestIter10Regression:
    def test_car_name_and_machine_number_roundtrip(self, admin_session, car_client_contract):
        cid = car_client_contract["item"]["id"]
        r = admin_session.get(f"{API}/items/car/{cid}")
        assert r.status_code == 200, r.text
        car = r.json()
        assert car.get("name") == "TEST_Ford Ranger Wildtrak"
        assert car.get("machine_number") == "ENG-ITER18-XX"
        assert car.get("chassis") == "CHS-ITER18-YY"
