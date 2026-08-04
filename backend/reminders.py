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

# Overdue days that trigger a reminder:
#   day  1 = "welcome to grace period" (masa tenggang di'ak) — softer tone
#   day  7 = first hard warning
#   day  9 = FINAL warning (last day before auction_ready per Article 4)
# Contracts move to auction_ready on day 11+, so day 9 is the last chance
# to send an overdue reminder that could still avoid the sasán going to leilaun.
REMINDER_DAYS = [1, 7, 9]

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

# Friendlier day-1 grace-period nudge — softer wording, explicit reassurance
# that the client still has a 10-day window before the item can go to auction.
_MSG_GRACE_EN = (
    "Fatin Penhores — Friendly Reminder\n"
    "Hello {name},\n"
    "Your contract {contract_number} was due yesterday. No stress — you're now\n"
    "in the 10-day grace period. You have {days_left} days to pay and keep\n"
    "your item.\n"
    "Amount owed today: ${loan} + {months}×${per_month} interest = ${total_due}.\n"
    "Come by the shop or WhatsApp us anytime: +670 78372678."
)

_MSG_GRACE_TET = (
    "Fatin Penhores — Lembransa Diak\n"
    "Ola {name},\n"
    "Kontratu {contract_number} nia due date liu ona horisehik. La preokupa —\n"
    "ita agora iha períodu toleránsia loron 10. Ita sei iha loron {days_left}\n"
    "tan atu selu no rai ita-nia sasán.\n"
    "Osan ohin: ${loan} + {months}×${per_month} juru = ${total_due}.\n"
    "Mai iha loja ka WhatsApp mai ami: +670 78372678."
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
    is_tet = (language or "en").lower() == "tet"
    # Day-1 grace-period start gets the friendlier template. Days ≥7 use the
    # standard hard reminder.
    try:
        due_check = date.fromisoformat(contract.get("due_date") or "")
        days_check = max(0, (today - due_check).days)
    except Exception:
        days_check = 0
    if days_check == 1:
        tmpl = _MSG_GRACE_TET if is_tet else _MSG_GRACE_EN
    else:
        tmpl = _MSG_TET if is_tet else _MSG_EN

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
        {"status": {"$in": ["overdue", "grace_period", "active"]}},
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
    """APScheduler hook — runs the async job in a fresh event loop.
    Records outcome to db.job_runs for the Dashboard Scheduler card."""
    import time
    from scheduler import _record_job_run_sync
    t0 = time.time()
    try:
        summary = asyncio.run(run_daily_reminders())
        _record_job_run_sync("daily_reminders", "ok", int((time.time() - t0) * 1000), {
            "sent": (summary or {}).get("sent"),
            "failed": (summary or {}).get("failed"),
            "skipped_already_sent": (summary or {}).get("skipped_already_sent"),
        })
    except Exception as exc:
        logger.exception("[reminders] top-level failure")
        _record_job_run_sync("daily_reminders", "failed", int((time.time() - t0) * 1000), {"error": str(exc)})



# =====================================================================
# Capital Installment Reminders (iter 61)
# Fires 7 / 3 / 1 day BEFORE each capital installment (and on the day
# itself). Notifies all admin users via email. Uses the same dedup log.
# =====================================================================
CAPITAL_REMINDER_DAYS = [7, 3, 1, 0]  # days *before* next_due


async def run_capital_reminders(force: bool = False) -> dict:
    """Scan funding sources for upcoming installments and email admins.

    A funding source is nudged when the days_until_due is in
    CAPITAL_REMINDER_DAYS (or when it's overdue and force=True).
    """
    from routes.finance import _repayment_split, _funding_schedule
    summary: dict = {"scanned": 0, "sent": 0, "skipped": 0, "errors": 0, "attempted": []}

    settings = await db.settings.find_one({}, {"_id": 0}) or {}
    if not settings.get("reminders_enabled", True):
        summary["disabled"] = True
        return summary

    today = datetime.now(timezone.utc).date()

    # Recipients — every admin user with an email.
    admin_users = await db.users.find(
        {"role": "admin"}, {"_id": 0, "id": 1, "email": 1, "name": 1}
    ).to_list(50)
    admin_recipients = [u for u in admin_users if u.get("email")]
    if not admin_recipients:
        summary["skipped"] += 1
        summary["reason"] = "no_admin_email"
        return summary

    sources = await db.funding_sources.find({}, {"_id": 0}).to_list(500)
    for src in sources:
        summary["scanned"] += 1
        # Compute paid totals for this source
        repaid = await db.funding_repayments.find({"source_id": src["id"]}, {"_id": 0}).to_list(500)
        p_paid = sum(_repayment_split(r)[0] for r in repaid)
        i_paid = sum(_repayment_split(r)[1] for r in repaid)
        sched = _funding_schedule(src, p_paid, i_paid, today=today)
        if sched["status"] == "closed":
            continue
        days_until = sched.get("days_until_due")
        if days_until is None:
            continue
        # Trigger buckets: 7, 3, 1, 0 days ahead — plus overdue (< 0) if force.
        if days_until in CAPITAL_REMINDER_DAYS:
            bucket = days_until
        elif force and days_until < 0:
            bucket = -1
        else:
            continue

        # Dedup — one email per source per bucket per day
        dedup_key = {
            "kind": "capital",
            "source_id": src["id"],
            "day_bucket": bucket,
            "date": today.isoformat(),
        }
        if not force and await db.reminder_log.find_one(dedup_key):
            summary["skipped"] += 1
            continue

        principal = float(src.get("principal_amount", 0) or 0)
        p_remaining = max(0.0, principal - p_paid)
        rate = float(src.get("interest_rate", 0) or 0)
        per_month = round(principal * rate / 100.0, 2) if src.get("interest_period") == "monthly" else 0.0
        subject_word = "Overdue" if bucket == -1 else ("Due today" if bucket == 0 else f"Due in {bucket} day(s)")
        subject = f"[Fatin Penhores] Capital installment — {subject_word} — {src.get('name','')}"
        html = _capital_reminder_html(
            source=src,
            principal_paid=p_paid,
            principal_remaining=p_remaining,
            interest_paid=i_paid,
            interest_remaining=sched["interest_remaining"],
            next_due_date=sched["next_due_date"],
            days_until=days_until,
            per_month_interest=per_month,
        )
        # Short WA/SMS-style body (~250 chars) for owner phone alerts.
        wa_body = (
            f"Fatin Penhores — Capital Reminder\n"
            f"{subject_word.upper()}: {src.get('name','')}\n"
            f"Next due: {sched['next_due_date']}\n"
            f"Principal left: ${p_remaining:,.2f}\n"
            f"Interest left: ${sched['interest_remaining']:,.2f}"
        )

        try:
            any_ok = False
            channels = []
            for user in admin_recipients:
                result = await email_svc.send_email(user["email"], subject, html)
                ok = result.get("status") == "sent"
                any_ok = any_ok or ok
                channels.append({"channel": "email", "recipient": user["email"], "status": result.get("status")})
            # Owner WhatsApp alert — optional, fires when both a phone is
            # configured in Settings AND the WhatsApp integration is set up.
            admin_phone = (settings.get("admin_alerts_phone") or "").strip()
            if admin_phone and wapp.is_configured(settings):
                wa_result = await wapp.send_text(admin_phone, wa_body, settings)
                wa_ok = wa_result.get("status") == "sent"
                any_ok = any_ok or wa_ok
                channels.append({"channel": "whatsapp", "recipient": admin_phone, "status": wa_result.get("status")})
            summary["attempted"].extend([
                {"source": src.get("name"), "bucket": bucket, **c} for c in channels
            ])
            if any_ok:
                summary["sent"] += 1
            else:
                summary["errors"] += 1
            await db.reminder_log.insert_one({
                "id": new_id(),
                **dedup_key,
                "source_name": src.get("name", ""),
                "success": any_ok,
                "channels": channels,
                "recipients": [u["email"] for u in admin_recipients] + ([admin_phone] if admin_phone else []),
                "created_at": utcnow_iso(),
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("[capital_reminders] failed for source %s", src.get("id"))
            summary["errors"] += 1
            await db.reminder_log.insert_one({
                "id": new_id(),
                **dedup_key,
                "success": False,
                "error": str(e),
                "created_at": utcnow_iso(),
            })

    return summary


def _capital_reminder_html(source: dict, principal_paid: float, principal_remaining: float,
                            interest_paid: float, interest_remaining: float, next_due_date: str,
                            days_until: int | None, per_month_interest: float) -> str:
    """Build a simple HTML email for the admin. Bilingual EN/TET."""
    name = source.get("name", "")
    principal = float(source.get("principal_amount", 0) or 0)
    urgency = "OVERDUE" if (days_until is not None and days_until < 0) else (
        "DUE TODAY" if days_until == 0 else f"Due in {days_until} day(s)"
    )
    return f"""
<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:560px;margin:auto;color:#1B2D5C;">
  <div style="background:#1B2D5C;color:#fff;padding:14px 18px;border-radius:6px 6px 0 0">
    <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;opacity:.8">Fatin Penhores · Capital Reminder</div>
    <div style="font-size:22px;font-weight:600;margin-top:4px">{urgency}</div>
  </div>
  <div style="background:#fff;border:1px solid #e7e5e4;border-top:0;padding:18px;border-radius:0 0 6px 6px">
    <p><b>{name}</b></p>
    <p>Next installment due date: <b>{next_due_date}</b></p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;margin-top:8px">
      <tr><td style="padding:4px 0;color:#57534E">Initial Loan</td><td style="text-align:right"><b>${principal:,.2f}</b></td></tr>
      <tr><td style="padding:4px 0;color:#57534E">Principal Paid</td><td style="text-align:right;color:#059669">${principal_paid:,.2f}</td></tr>
      <tr><td style="padding:4px 0;color:#57534E">Principal Remaining</td><td style="text-align:right;color:#C17767"><b>${principal_remaining:,.2f}</b></td></tr>
      <tr><td style="padding:4px 0;color:#57534E">Interest Paid</td><td style="text-align:right;color:#059669">${interest_paid:,.2f}</td></tr>
      <tr><td style="padding:4px 0;color:#57534E">Interest Remaining</td><td style="text-align:right">${interest_remaining:,.2f}</td></tr>
      <tr><td style="padding:4px 0;color:#57534E">Interest / month</td><td style="text-align:right">${per_month_interest:,.2f}</td></tr>
    </table>
    <p style="font-size:12px;color:#57534E;margin-top:16px;line-height:1.5">
      Log in to the admin console to record the repayment. Principal reduces
      Capital Outstanding + Cash on Hand. Interest is booked as an expense and
      reduces Net Profit.
    </p>
  </div>
  <p style="font-size:11px;color:#8b8680;text-align:center;margin-top:10px">
    Fatin Penhores Unipessoal, Lda · Dili, Timor-Leste
  </p>
</div>
"""


def run_capital_reminders_sync() -> None:
    """APScheduler hook — runs the async capital-reminder job.
    Records outcome to db.job_runs for the Dashboard Scheduler card."""
    import time
    from scheduler import _record_job_run_sync
    t0 = time.time()
    try:
        summary = asyncio.run(run_capital_reminders())
        _record_job_run_sync("capital_reminders", "ok", int((time.time() - t0) * 1000), {
            "sent": (summary or {}).get("sent"),
            "scanned": (summary or {}).get("scanned"),
        })
    except Exception as exc:
        logger.exception("[capital_reminders] top-level failure")
        _record_job_run_sync("capital_reminders", "failed", int((time.time() - t0) * 1000), {"error": str(exc)})