"""Daily WhatsApp overdue reminders (iter17).

Fires at 09:00 Timor-Leste local time (UTC+9 → 00:00 UTC).
Targets contracts overdue by exactly 7 or 9 days (first + final warning).

Design:
- On/off toggled by admin (settings.reminders_enabled).
- Duplicate prevention: writes to db.reminder_log — one entry per
  (contract_id, day_bucket) combination so re-runs never double-send.
- Skips sending when WhatsApp isn't configured (logs a warning).
- Idempotent: a single reminder per contract per bucket per contract cycle.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, date, timedelta
from dateutil.relativedelta import relativedelta

from deps import db, utcnow_iso, new_id, months_billed
import whatsapp as wapp

logger = logging.getLogger(__name__)

# Overdue days that trigger a reminder (day 7 = first warning, day 9 = final)
REMINDER_DAYS = [7, 9]

# Message templates — kept short to fit WhatsApp free-form limits + Timor mobile screens.
# Placeholder tokens:
#   {name}, {contract_number}, {days} — how many days past the due date
#   {days_left} — days remaining before the item goes to auction
#   {loan}, {per_month} — loan amount and per-month interest ($)
#   {months} — billing months owed today (Rule A)
#   {interest_total} — {months} × {per_month}
#   {total_due} — {loan} + {interest_total}
#   {next_month_date} — when the next month of interest kicks in
#   {next_interest_total} — {interest_total} + {per_month}
_MSG_EN = (
    "Fatin Penhores — Overdue Notice\n"
    "Hello {name},\n"
    "Contract {contract_number} is {days} days overdue.\n"
    "Owed today: ${loan} + {months}×${per_month} interest = ${total_due}.\n"
    "On {next_month_date} interest rises to ${next_interest_total}.\n"
    "Please pay within {days_left} more days to avoid auction.\n"
    "WhatsApp: +670 78372678"
)

_MSG_TET = (
    "Fatin Penhores — Notifikasaun Atrazu\n"
    "Ola {name},\n"
    "Kontratu {contract_number} atrazu ona loron {days}.\n"
    "Osan tenke selu ohin: ${loan} + {months}×${per_month} juru = ${total_due}.\n"
    "Iha loron {next_month_date} juru sae ba ${next_interest_total}.\n"
    "Favor selu iha loron {days_left} tan atu evita leilão.\n"
    "WhatsApp: +670 78372678"
)


def _short_contract(number: str | None) -> str:
    """CTR-2026-0042 → CT-2026-42 for compact display in messages."""
    if not number:
        return ""
    import re
    m = re.match(r"^CTR-(\d{4})-0*(\d+)$", number)
    return f"CT-{m.group(1)}-{m.group(2)}" if m else number


def build_reminder_body(contract: dict, client_name: str, language: str, today: date | None = None) -> dict:
    """Build the WhatsApp reminder message body for a contract using Rule A math.

    Returns dict with `body`, plus metadata (days, months, total_due, next_month_date)
    that the UI can display alongside the preview.

    Used by:
    - Daily scheduler (run_daily_reminders)
    - Ad-hoc "Preview & Send" endpoint (whatsapp/preview / whatsapp/adhoc-send)
    """
    today = today or datetime.now(timezone.utc).date()
    tmpl = _MSG_TET if (language or "en").lower() == "tet" else _MSG_EN

    loan = float(contract.get("loan_amount", 0) or 0)
    rate = float(contract.get("interest_rate", 0) or 0)
    per_month = round(loan * rate / 100.0, 2)
    try:
        start = date.fromisoformat(contract["contract_date"])
    except Exception:
        start = today
    try:
        due = date.fromisoformat(contract.get("due_date") or start.isoformat())
    except Exception:
        due = start
    days = max(0, (today - due).days)
    months = months_billed(start, today)
    interest_total = round(per_month * months, 2)
    total_due = round(loan + interest_total, 2)
    next_month_date = (start + relativedelta(months=months) + timedelta(days=1)).isoformat()
    next_interest_total = round(interest_total + per_month, 2)

    body = tmpl.format(
        name=client_name or "",
        contract_number=_short_contract(contract.get("contract_number")),
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
    return {
        "body": body,
        "days": days,
        "months": months,
        "per_month": per_month,
        "total_due": total_due,
        "next_month_date": next_month_date,
        "language": (language or "en").lower(),
    }


async def _sent_today(contract_id: str, day_bucket: int) -> bool:
    """Return True if a reminder for this contract & bucket was already sent this cycle."""
    today = datetime.now(timezone.utc).date().isoformat()
    existing = await db.reminder_log.find_one({
        "contract_id": contract_id,
        "day_bucket": day_bucket,
        "date": today,
    })
    return existing is not None


async def _mark_sent(contract_id: str, day_bucket: int, phone: str, ok: bool, error: str | None = None):
    await db.reminder_log.insert_one({
        "id": new_id(),
        "contract_id": contract_id,
        "day_bucket": day_bucket,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "phone": phone,
        "success": ok,
        "error": error or "",
        "created_at": utcnow_iso(),
    })


async def run_daily_reminders() -> dict:
    """Main job — scans overdue contracts and sends WhatsApp reminders.

    Returns a summary dict for the admin UI. Never raises."""
    logger.info("[reminders] daily job starting")
    summary: dict = {"scanned": 0, "sent": 0, "skipped": 0, "errors": 0, "attempted": []}

    # Load settings — early exit if reminders disabled or WhatsApp not configured
    settings = await db.settings.find_one({}, {"_id": 0}) or {}
    if not settings.get("reminders_enabled", True):
        summary["disabled"] = True
        await _write_run_summary(summary)
        logger.info("[reminders] reminders_enabled=False — skipping run")
        return summary

    # We import here to avoid circular import at module load
    from deps import db as _db  # noqa: F401
    # Locally recompute overdue days rather than pulling every contract through _recompute
    today = datetime.now(timezone.utc).date()
    contracts = await db.contracts.find(
        {"status": {"$in": ["overdue", "active"]}},
        {"_id": 0, "id": 1, "contract_number": 1, "client_id": 1, "due_date": 1,
         "contract_date": 1, "loan_amount": 1, "interest_rate": 1},
    ).to_list(2000)

    lang = (settings.get("lang") or "en").lower()

    for c in contracts:
        summary["scanned"] += 1
        due = c.get("due_date")
        if not due:
            continue
        try:
            days = (today - date.fromisoformat(due)).days
        except Exception:
            continue
        if days not in REMINDER_DAYS:
            continue
        if await _sent_today(c["id"], days):
            summary["skipped"] += 1
            continue

        client = await db.clients.find_one({"id": c["client_id"]}, {"_id": 0, "full_name": 1, "phone": 1})
        if not client or not client.get("phone"):
            summary["skipped"] += 1
            continue

        # Compute the same interest math the receipt PDF shows.
        info = build_reminder_body(c, client.get("full_name", ""), lang, today=today)
        body = info["body"]

        try:
            if not wapp.is_configured(settings):
                # No creds — record as skipped, not error (so admin sees the reason)
                await _mark_sent(c["id"], days, client["phone"], False, "whatsapp_not_configured")
                summary["skipped"] += 1
                continue
            result = await wapp.send_text(client["phone"], body, settings)
            ok = result.get("status") == "sent"
            await _mark_sent(c["id"], days, client["phone"], ok, None if ok else str(result))
            if ok:
                summary["sent"] += 1
                summary["attempted"].append({"contract": c.get("contract_number"), "days": days, "phone": client["phone"]})
            else:
                summary["errors"] += 1
        except Exception as e:  # noqa: BLE001
            logger.exception("[reminders] send failed for %s", c.get("contract_number"))
            await _mark_sent(c["id"], days, client.get("phone", ""), False, str(e))
            summary["errors"] += 1

    await _write_run_summary(summary)
    logger.info("[reminders] done — %s", summary)
    return summary


async def _write_run_summary(summary: dict) -> None:
    """Persist the last-run metadata so admin UI can display it in Settings."""
    await db.settings.update_one(
        {},
        {"$set": {
            "reminders_last_run_at": utcnow_iso(),
            "reminders_last_run_summary": {
                "scanned": summary.get("scanned", 0),
                "sent": summary.get("sent", 0),
                "skipped": summary.get("skipped", 0),
                "errors": summary.get("errors", 0),
                "disabled": summary.get("disabled", False),
            },
        }},
        upsert=True,
    )


def run_daily_reminders_sync() -> None:
    """APScheduler hook — runs the async job in a fresh event loop."""
    try:
        asyncio.run(run_daily_reminders())
    except Exception:
        logger.exception("[reminders] top-level failure")
