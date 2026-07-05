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
from services import _recompute_contract_status
import whatsapp as wapp
import email_svc

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
    """Build the WhatsApp reminder message body for a contract.

    Uses Rule B (hybrid) interest math when the caller supplies a recomputed
    contract (has `interest_amount`, `per_month_interest`, `principal_remaining`,
    `months_elapsed`). Otherwise falls back to a simple `loan × rate` approximation.

    Used by:
    - Daily scheduler (run_daily_reminders) — passes RECOMPUTED contract
    - Ad-hoc "Preview & Send" endpoint (whatsapp/preview) — passes RECOMPUTED contract
    """
    today = today or datetime.now(timezone.utc).date()
    tmpl = _MSG_TET if (language or "en").lower() == "tet" else _MSG_EN

    loan = float(contract.get("loan_amount", 0) or 0)
    rate = float(contract.get("interest_rate", 0) or 0)
    try:
        start = date.fromisoformat(contract["contract_date"])
    except Exception:
        start = today
    try:
        due = date.fromisoformat(contract.get("due_date") or start.isoformat())
    except Exception:
        due = start
    days = max(0, (today - due).days)

    # Prefer values from the recomputed contract (Rule B hybrid math). Fall back
    # to a simple approximation when the caller didn't recompute.
    has_recomputed = "interest_amount" in contract and "months_elapsed" in contract
    if has_recomputed:
        months = int(contract.get("months_elapsed") or 1)
        interest_total = float(contract.get("interest_amount", 0) or 0)
        per_month = float(contract.get("per_month_interest", 0) or 0)
        per_month_next = float(contract.get("per_month_interest_next", per_month) or per_month)
        principal_remaining = float(contract.get("principal_remaining", loan) or loan)
        # Show the OUTSTANDING total (principal + accrued interest still owed),
        # not just loan+interest — reminders should reflect what the client
        # actually needs to pay today after any partial payments.
        total_due = float(contract.get("total_due", loan + interest_total) or (loan + interest_total))
        # Loan shown in the body should reflect remaining principal so the
        # numbers add up: "$X remaining + N × $Y interest = $Z".
        loan_display = principal_remaining
    else:
        months = months_billed(start, today)
        per_month = round(loan * rate / 100.0, 2)
        per_month_next = per_month
        interest_total = round(per_month * months, 2)
        total_due = round(loan + interest_total, 2)
        loan_display = loan

    next_month_date = (start + relativedelta(months=months) + timedelta(days=1)).isoformat()
    next_interest_total = round(interest_total + per_month_next, 2)

    body = tmpl.format(
        name=client_name or "",
        contract_number=_short_contract(contract.get("contract_number")),
        days=days,
        days_left=max(0, 10 - days),
        loan=f"{loan_display:,.2f}",
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

        client = await db.clients.find_one(
            {"id": c["client_id"]},
            {"_id": 0, "full_name": 1, "phone": 1, "email": 1},
        )
        if not client:
            summary["skipped"] += 1
            continue

        # Recompute so Rule B (hybrid) math is applied and message text is accurate.
        c = await _recompute_contract_status(c)

        # Compute the same interest math the receipt PDF shows.
        info = build_reminder_body(c, client.get("full_name", ""), lang, today=today)
        body = info["body"]

        phone = (client.get("phone") or "").strip()
        email_addr = (client.get("email") or "").strip()

        # Preferred channel: WhatsApp (matches business habits & is cheaper).
        # Fallback: email — only fires when phone is missing (per admin choice).
        try:
            if phone and wapp.is_configured(settings):
                result = await wapp.send_text(phone, body, settings)
                ok = result.get("status") == "sent"
                await _mark_sent(c["id"], days, phone, ok, None if ok else str(result))
                if ok:
                    summary["sent"] += 1
                    summary["attempted"].append({
                        "contract": c.get("contract_number"),
                        "days": days,
                        "channel": "whatsapp",
                        "recipient": phone,
                    })
                else:
                    summary["errors"] += 1
            elif not phone and email_addr:
                # Email fallback — client has no phone number on file.
                subject, html = email_svc.render_overdue_reminder(
                    client_name=client.get("full_name", ""),
                    contract_number=c.get("contract_number", ""),
                    days_overdue=days,
                    total_due=info["total_due"],
                    per_month_interest=info["per_month"],
                    months=info["months"],
                    next_month_date=info["next_month_date"],
                    days_left=max(0, 10 - days),
                )
                result = await email_svc.send_email(email_addr, subject, html)
                ok = result.get("status") == "sent"
                await _mark_sent(c["id"], days, email_addr, ok, None if ok else str(result))
                if ok:
                    summary["sent"] += 1
                    summary["attempted"].append({
                        "contract": c.get("contract_number"),
                        "days": days,
                        "channel": "email",
                        "recipient": email_addr,
                    })
                elif result.get("status") == "mocked":
                    summary["skipped"] += 1
                else:
                    summary["errors"] += 1
            else:
                # No usable channel — record so admin can see why nothing sent.
                reason = "no_phone_or_email" if not (phone or email_addr) else "whatsapp_not_configured"
                await _mark_sent(c["id"], days, phone or email_addr or "—", False, reason)
                summary["skipped"] += 1
        except Exception as e:  # noqa: BLE001
            logger.exception("[reminders] send failed for %s", c.get("contract_number"))
            await _mark_sent(c["id"], days, phone or email_addr, False, str(e))
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
