"""Owner alerts + visitor WhatsApp subscriptions (auction-date reminders, new-listing alerts)."""
from __future__ import annotations

import asyncio
import logging
from html import escape

import email_svc
import whatsapp as wapp
from deps import db, new_id, utcnow_iso
from services import _decrypted_settings, ITEM_KINDS

log = logging.getLogger("subscribers")

KIND_LABEL = {
    "car": ("karreta", "car"), "motorcycle": ("motor", "motorcycle"),
    "electronic": ("eletróniku", "electronics"), "pezadu": ("ekipamentu pezadu", "heavy equipment"),
}


def clean_phone(p: str) -> str:
    digits = "".join(ch for ch in (p or "") if ch.isdigit())
    if len(digits) in (7, 8):  # local Timor-Leste number → add country code
        digits = "670" + digits
    return digits


async def _log_wa(phone: str, template: str, body: str, result: dict, **extra) -> None:
    await db.whatsapp_log.insert_one({
        "id": new_id(), "client_phone": phone, "language": "tet+en", "template": template, "body": body,
        "result": result, "meta_message_id": result.get("meta_message_id"),
        "delivery_status": result.get("status") or "queued", "sent_at": result.get("sent_at"),
        "created_at": utcnow_iso(), **extra,
    })


async def notify_admins(subject: str, text: str, html: str | None = None) -> dict:
    """Email every admin + WhatsApp the owner number (admin_alerts_phone) when configured."""
    settings = await _decrypted_settings()
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "email": 1}).to_list(50)
    channels = []
    for u in admins:
        if u.get("email"):
            r = await email_svc.send_email(u["email"], subject, html or f"<p>{escape(text)}</p>")
            channels.append({"channel": "email", "to": u["email"], "status": r.get("status")})
    phone = clean_phone(settings.get("admin_alerts_phone") or "")
    if phone:
        r = await wapp.send_text(phone, text, settings)
        await _log_wa(phone, "admin_alert", text, r, subject=subject)
        channels.append({"channel": "whatsapp", "to": phone, "status": r.get("status")})
    return {"channels": channels}


async def broadcast(query: dict, template: str, body_fn) -> dict:
    """Send a WhatsApp text to every active subscriber matching `query`. body_fn(sub) -> str."""
    settings = await _decrypted_settings()
    subs = await db.subscribers.find({"active": True, **query}, {"_id": 0}).to_list(5000)
    sent = 0
    for sub in subs:
        body = body_fn(sub)
        try:
            r = await wapp.send_text(sub["phone"], body, settings)
        except Exception as exc:  # never let one bad number stop the batch
            r = {"status": "failed", "error": str(exc)}
        await _log_wa(sub["phone"], template, body, r, subscriber_id=sub["id"])
        sent += r.get("status") in ("sent", "mocked")
    return {"recipients": len(subs), "sent": sent}


def fire_and_forget(coro) -> None:
    """Run a notification in the background so request handlers never wait on WhatsApp."""
    async def _run():
        try:
            await coro
        except Exception:
            log.exception("background notification failed")
    asyncio.get_event_loop().create_task(_run())


def auction_date_body(date_str: str):
    def _body(_sub):
        return (f"Fatin Penhores: leilaun tuir mai sei hala'o iha {date_str} (tuku 09:00) iha Caicoli, Dili. "
                f"Haree sasán sira: fatinpenhores.tl/auction\n\n"
                f"Fatin Penhores: our next auction is on {date_str} at 09:00 in Caicoli, Dili. See the items: /auction")
    return _body


def new_listing_body(kind: str, year, price):
    tet, en = KIND_LABEL.get(kind, ("sasán", "item"))
    yr = f" ({year})" if year else ""
    def _body(_sub):
        return (f"Fatin Penhores: {tet} foun{yr} tama ona iha lista leilaun — folin hahú USD {price:,.0f}. "
                f"Haree: /auction\n\nFatin Penhores: a new {en}{yr} was just listed for auction — starting price USD {price:,.0f}. See: /auction")
    return _body


def kinds_valid(kinds: list[str]) -> list[str]:
    return [k for k in dict.fromkeys(kinds or []) if k in ITEM_KINDS]


def auction_day_reminder_body(s: dict, auction_date: str) -> str:
    from services import DEFAULT_SETTINGS
    address = s.get("contact_address") or DEFAULT_SETTINGS["contact_address"]
    hours = s.get("contact_hours") or DEFAULT_SETTINGS["contact_hours"]
    return (f"Fatin Penhores: LEMBRA — leilaun hala'o AVAN, {auction_date}, hahú tuku 09:00. "
            f"Fatin: {address}. Loke: {hours}. Lori ita-boot nia ID. Haree lista: /auction\n\n"
            f"Fatin Penhores: REMINDER — the auction is TOMORROW, {auction_date}, starting 09:00. "
            f"Venue: {address}. Hours: {hours}. Bring your ID. Items: /auction")


async def auction_day_reminder_preview() -> dict:
    """What the scheduler would send: date, exact text, recipient count, last-sent status."""
    from datetime import date, timedelta
    from services import get_settings_doc
    s = await get_settings_doc()
    auction_date = (s.get("next_auction_date") or "").strip()
    recipients = await db.subscribers.count_documents({"active": True, "auction_reminder": True})
    last = await db.whatsapp_log.find({"template": "auction_day_reminder"}, {"_id": 0, "created_at": 1, "delivery_status": 1}) \
        .sort("created_at", -1).limit(1).to_list(1)
    last_sent = await db.whatsapp_log.count_documents({"template": "auction_day_reminder", "delivery_status": {"$in": ["sent", "mocked"]}})
    send_on = (date.fromisoformat(auction_date) - timedelta(days=1)).isoformat() if auction_date else None
    return {
        "next_auction_date": auction_date or None,
        "send_on": send_on,
        "send_time_local": "10:00 Timor-Leste",
        "body": auction_day_reminder_body(s, auction_date or "<date>") if auction_date else None,
        "recipients": recipients,
        "sent_for": s.get("auction_day_reminder_sent_for") or None,
        "already_sent": bool(auction_date) and s.get("auction_day_reminder_sent_for") == auction_date,
        "last_sent_at": last[0]["created_at"] if last else None,
        "last_status": last[0].get("delivery_status") if last else None,
        "total_sent": last_sent,
        "whatsapp_configured": bool(s.get("whatsapp_token") and s.get("whatsapp_phone_id")),
        "test_phone": clean_phone(s.get("admin_alerts_phone") or ""),
    }


async def send_auction_day_reminder_test(phone: str) -> dict:
    """Send the exact reminder text to one admin phone (never touches the sent_for marker)."""
    from services import get_settings_doc
    settings = await _decrypted_settings()
    s = await get_settings_doc()
    auction_date = (s.get("next_auction_date") or "").strip()
    if not auction_date:
        return {"status": "skipped", "reason": "no next_auction_date"}
    body = auction_day_reminder_body(s, auction_date)
    try:
        r = await wapp.send_text(phone, body, settings)
    except Exception as exc:
        r = {"status": "failed", "error": str(exc)}
    await _log_wa(phone, "auction_day_reminder_test", body, r)
    return {"status": r.get("status"), "to": phone, "body": body}


async def run_auction_day_reminder(force: bool = False) -> dict:
    """Day-before reminder to auction-date subscribers (09:00 start, shop address). Idempotent per date."""
    from datetime import date, timedelta
    from services import get_settings_doc
    s = await get_settings_doc()
    auction_date = (s.get("next_auction_date") or "").strip()
    if not auction_date:
        return {"status": "skipped", "reason": "no next_auction_date"}
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    if auction_date != tomorrow and not force:
        return {"status": "skipped", "reason": f"auction {auction_date} is not tomorrow"}
    if s.get("auction_day_reminder_sent_for") == auction_date and not force:
        return {"status": "skipped", "reason": "already sent"}
    body = auction_day_reminder_body(s, auction_date)
    result = await broadcast({"auction_reminder": True}, "auction_day_reminder", lambda _sub: body)
    await db.settings.update_one({"id": "singleton"}, {"$set": {"auction_day_reminder_sent_for": auction_date}}, upsert=True)
    return {"status": "sent", "auction_date": auction_date, **result}


def run_auction_day_reminder_sync() -> None:
    import time
    from scheduler import _record_job_run_sync
    t0 = time.time()
    try:
        summary = asyncio.run(run_auction_day_reminder())
        _record_job_run_sync("auction_day_reminder", "ok", int((time.time() - t0) * 1000), summary)
    except Exception as exc:
        log.exception("[auction reminder] failure")
        _record_job_run_sync("auction_day_reminder", "failed", int((time.time() - t0) * 1000), {"error": str(exc)})
