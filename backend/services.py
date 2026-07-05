"""Cross-domain service helpers.

Moved out of `server.py` during the Phase 2 refactor so router modules under
`routes/` can safely import shared logic without pulling in circular deps.

Contains:
- Interest / contract math (`_recompute_contract_status`)
- Item fetch helper (`_fetch_item`)
- Settings load/decrypt (`get_settings_doc`, `_decrypted_settings`, `DEFAULT_SETTINGS`)
- WhatsApp reminder helpers (`_send_reminder_for_contract`, `_wa_template_name`,
  `_wa_lang_code`)
- Small utility helpers (`_today_iso`)
"""
from __future__ import annotations

from datetime import datetime, timezone, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional

from deps import (
    db,
    utcnow_iso,
    new_id,
    COLLECTION_MAP,
    months_billed as _months_billed,
)
from pdf_utils import DEFAULT_TNC_EN, DEFAULT_TNC_TET
import whatsapp as wapp


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
ITEM_KINDS = ("car", "motorcycle", "electronic", "pezadu")

DEFAULT_SETTINGS = {
    "id": "singleton",
    "interest_rate_car": 10,
    "interest_rate_motorcycle": 15,
    "interest_rate_electronic": 15,
    "interest_rate_pezadu": 10,
    "terms_and_conditions_en": DEFAULT_TNC_EN,
    "terms_and_conditions_tet": DEFAULT_TNC_TET,
    "whatsapp_template_en": "due_date_reminder",
    "whatsapp_template_tet": "due_date_reminder_tet",
    "whatsapp_token": "",
    "whatsapp_phone_id": "",
    "reminder_days_before": 3,
    "reminders_enabled": True,
}


# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------
def _today_iso() -> str:
    return date.today().isoformat()


def _ym_from_iso(iso: str | None) -> tuple[int | None, int | None]:
    if not iso or len(iso) < 7:
        return None, None
    try:
        return int(iso[:4]), int(iso[5:7])
    except Exception:
        return None, None


def _apply_date_filter(rows: list[dict], date_field: str, month: Optional[int], year: Optional[int]) -> list[dict]:
    if not month and not year:
        return rows
    out = []
    for r in rows:
        y, m = _ym_from_iso(r.get(date_field))
        if year and y != year:
            continue
        if month and m != month:
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------
async def _fetch_item(kind: str, iid: str) -> Optional[dict]:
    if kind not in ITEM_KINDS:
        return None
    return await db[COLLECTION_MAP[kind]].find_one({"id": iid}, {"_id": 0})


# ---------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------
async def get_settings_doc() -> dict:
    doc = await db.settings.find_one({"id": "singleton"}, {"_id": 0})
    if not doc:
        await db.settings.insert_one(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()
    return {**DEFAULT_SETTINGS, **doc}


async def _decrypted_settings() -> dict:
    """Internal: return settings with whatsapp_token decrypted for backend use only."""
    from encryption import decrypt_token
    s = await get_settings_doc()
    s["whatsapp_token"] = decrypt_token(s.get("whatsapp_token", ""))
    return s


# ---------------------------------------------------------------------
# Contract math (Rule A — strict calendar month + 1 grace day)
# ---------------------------------------------------------------------
async def _recompute_contract_status(contract: dict) -> dict:
    """Compute live status, principal/interest split, penalty, and next milestone dates.

    Interest model (Article 4 — Rule A: Strict calendar month + 1 grace day):
    - The first monthly billing period is ALWAYS charged (minimum 1 month interest).
    - Payment on the monthly anniversary of the start date → same month is billed.
    - Payment 1 day after the anniversary → a new full month kicks in.
    """
    payments = await db.payments.find({"contract_id": contract["id"]}, {"_id": 0}).to_list(500)
    loan = float(contract["loan_amount"])
    rate = float(contract["interest_rate"])
    per_month_interest = round(loan * rate / 100.0, 2)

    today_iso = _today_iso()
    try:
        contract_start = date.fromisoformat(contract["contract_date"])
        due = date.fromisoformat(contract["due_date"])
    except Exception:
        contract_start = date.today()
        due = date.today()
    today_dt = date.today()
    effective_end = max(due, today_dt)
    months_elapsed = _months_billed(contract_start, effective_end)
    interest = round(per_month_interest * months_elapsed, 2)

    next_interest_date = contract_start + relativedelta(months=months_elapsed) + timedelta(days=1)
    while next_interest_date <= today_dt:
        next_interest_date = next_interest_date + relativedelta(months=1)

    is_overdue = contract.get("due_date", today_iso) < today_iso
    full_penalty = round(loan * 0.10, 2) if (is_overdue and contract.get("status") != "auction") else 0.0

    interest_paid = 0.0
    principal_paid = 0.0
    penalty_paid = 0.0
    for p in sorted(payments, key=lambda x: (x.get("date", ""), x.get("created_at", ""))):
        amt = float(p.get("amount", 0))
        ptype = p.get("type", "partial")
        if ptype == "disbursement":
            continue
        if ptype == "interest_only":
            take = min(amt, max(0.0, interest - interest_paid))
            interest_paid += take
            extra = amt - take
            if extra > 0:
                principal_paid += extra
        elif ptype == "partial":
            principal_paid += amt
        elif ptype == "full":
            take = max(0.0, interest - interest_paid)
            interest_paid += min(amt, take)
            principal_paid += max(0.0, amt - take)
        elif ptype == "overdue_full":
            pen_remaining = max(0.0, full_penalty - penalty_paid)
            take_pen = min(amt, pen_remaining)
            penalty_paid += take_pen
            rem = amt - take_pen
            take_int = min(rem, max(0.0, interest - interest_paid))
            interest_paid += take_int
            rem -= take_int
            principal_paid += max(0.0, rem)
        elif ptype == "overdue_interest_pen":
            pen_remaining = max(0.0, full_penalty - penalty_paid)
            take_pen = min(amt, pen_remaining)
            penalty_paid += take_pen
            rem = amt - take_pen
            take_int = min(rem, max(0.0, interest - interest_paid))
            interest_paid += take_int
        elif ptype == "overdue_penalty_only":
            pen_remaining = max(0.0, full_penalty - penalty_paid)
            penalty_paid += min(amt, pen_remaining)

    principal_paid = min(principal_paid, loan)
    interest_paid = min(interest_paid, interest)
    penalty_paid = min(penalty_paid, full_penalty)
    principal_remaining = round(max(0.0, loan - principal_paid), 2)
    interest_remaining = round(max(0.0, interest - interest_paid), 2)
    penalty_remaining = round(max(0.0, full_penalty - penalty_paid), 2)

    redeemed = (principal_remaining + interest_remaining + penalty_remaining) <= 0.01
    penalty = penalty_remaining

    days_overdue = 0
    if is_overdue:
        try:
            days_overdue = (date.today() - date.fromisoformat(contract["due_date"])).days
        except Exception:
            days_overdue = 0

    total_due = round(principal_remaining + interest_remaining + penalty, 2)

    if contract.get("status") == "auction":
        status = "auction"
    elif contract.get("status") == "sold":
        status = "sold"
    elif redeemed:
        status = "redeemed"
    elif is_overdue and days_overdue > 10:
        status = "auction_ready"
    elif is_overdue:
        status = "overdue"
    else:
        status = "active"

    if status != contract.get("status"):
        await db.contracts.update_one({"id": contract["id"]}, {"$set": {"status": status}})

    contract["status"] = status
    contract["paid_amount"] = round(principal_paid + interest_paid, 2)
    contract["principal_paid"] = round(principal_paid, 2)
    contract["interest_paid"] = round(interest_paid, 2)
    contract["principal_remaining"] = principal_remaining
    contract["interest_remaining"] = interest_remaining
    contract["interest_amount"] = interest
    contract["per_month_interest"] = per_month_interest
    contract["months_elapsed"] = months_elapsed
    contract["next_interest_date"] = next_interest_date.isoformat()
    contract["penalty"] = penalty
    contract["penalty_paid"] = round(penalty_paid, 2)
    contract["penalty_full"] = full_penalty
    contract["days_overdue"] = days_overdue
    contract["total_due"] = total_due
    contract["remaining_balance"] = total_due
    return contract


# ---------------------------------------------------------------------
# WhatsApp templated-reminder helpers (used by /whatsapp/send + scheduler)
# ---------------------------------------------------------------------
def _wa_template_name(settings: dict, language: str) -> str:
    key = "whatsapp_template_en" if language == "en" else "whatsapp_template_tet"
    return settings.get(key) or settings.get("whatsapp_template_en") or "due_date_reminder"


def _wa_lang_code(language: str) -> str:
    return "en" if language == "en" else "pt_PT"


async def _send_reminder_for_contract(contract: dict, language: str, settings: dict, actor: dict) -> dict:
    client_doc = await db.clients.find_one({"id": contract["client_id"]}, {"_id": 0}) or {}
    phone = client_doc.get("phone", "")
    name = client_doc.get("full_name", "Client")
    cnum = contract.get("contract_number", "")
    due = contract.get("due_date", "")
    remaining = float(contract.get("remaining_balance", 0) or 0)
    params = [name, cnum, due, f"USD {remaining:,.2f}"]
    template = _wa_template_name(settings, language)
    lang_code = _wa_lang_code(language)
    result = await wapp.send_template(phone, template, lang_code, params, settings)
    await db.whatsapp_log.insert_one({
        "id": new_id(),
        "contract_id": contract["id"],
        "contract_number": cnum,
        "client_id": client_doc.get("id"),
        "client_phone": phone,
        "language": language,
        "template": template,
        "parameters": params,
        "result": result,
        "actor_id": actor.get("id"),
        "created_at": utcnow_iso(),
    })
    return result
