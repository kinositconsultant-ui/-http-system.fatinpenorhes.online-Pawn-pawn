"""Pinned View Alert Digest.

Once a day the scheduler evaluates every user's *pinned* saved report views
that have an `alert_threshold`. If the current row count exceeds the
threshold, a "digest" is prepared for that user. Digests are:

  1. Persisted to the `alert_digests` collection (so we have history + an
     admin preview endpoint) with a UTC timestamp and per-view details.
  2. Emailed to the user's `email` via `email_svc.send_email` (falls back to
     MOCKED when RESEND_API_KEY is not configured — no crash).

The daily scheduler job (`run_alert_digest_job_sync` in this file) is wired
into `scheduler.py` and runs at 23:00 UTC (~08:00 Timor next day).
Admin can preview the digest for their own user at any time via
GET /api/alerts/preview.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from deps import db, new_id, utcnow_iso, get_current_user, require_admin
from routes.reports import REPORT_BUILDERS
from email_svc import send_email, is_configured as email_configured, BRAND, FOOTER_HTML

router = APIRouter()
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------
async def _count_rows_for_view(view: dict) -> int:
    """Return the current row count for a saved view (server-authoritative)."""
    builder = REPORT_BUILDERS.get(view.get("tab"))
    if not builder:
        return 0
    f = view.get("filters") or {}
    params = {
        "month": _to_int(f.get("month")),
        "year": _to_int(f.get("year")),
        "category": f.get("category") or None,
        "sub_category": f.get("sub_category") or None,
    }
    try:
        data = await builder(params)
    except Exception:
        log.exception("[alerts] report builder failed for view %s", view.get("id"))
        return 0
    rows = data.get("rows") or []
    return len(rows)


def _to_int(v) -> Optional[int]:
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


async def compute_user_digest(user: dict) -> dict:
    """Build (but do not send) a digest for a single user.

    Result shape:
    { user_id, email, name, breaches: [ {view_id, name, tab, threshold, count, over_by} ],
      total_views_checked, generated_at_utc }
    """
    views = await db.report_views.find(
        {"user_id": user["id"], "pinned": True, "alert_threshold": {"$ne": None}},
        {"_id": 0},
    ).to_list(200)

    breaches: list[dict] = []
    for v in views:
        try:
            th = int(v.get("alert_threshold"))
        except (TypeError, ValueError):
            continue
        count = await _count_rows_for_view(v)
        if count > th:
            breaches.append({
                "view_id": v["id"],
                "name": v.get("name"),
                "tab": v.get("tab"),
                "threshold": th,
                "count": count,
                "over_by": count - th,
                "filters": v.get("filters") or {},
                "sort": v.get("sort"),
            })
    return {
        "user_id": user["id"],
        "email": user.get("email"),
        "name": user.get("name") or user.get("email"),
        "breaches": breaches,
        "total_views_checked": len(views),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------
def render_digest_email(digest: dict) -> tuple[str, str]:
    """Return (subject, html) — a compact, mobile-friendly alert email."""
    subject = f"{BRAND} — {len(digest['breaches'])} view(s) over threshold"
    rows_html = ""
    for b in digest["breaches"]:
        rows_html += f"""
        <tr>
          <td style="padding:10px 8px;border-bottom:1px solid #eee">
            <div style="font-weight:600;color:#0F1B3A">{b['name']}</div>
            <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:1px">{b['tab'].replace('-', ' ')}</div>
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right">
            <div style="font-size:22px;font-weight:700;color:#b91c1c">{b['count']}</div>
            <div style="font-size:11px;color:#6b7280">alert &gt; {b['threshold']}</div>
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right">
            <div style="font-size:12px;color:#b91c1c;font-weight:600">+{b['over_by']}</div>
            <div style="font-size:10px;color:#9ca3af">over</div>
          </td>
        </tr>"""

    html = f"""
<!doctype html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width:620px; margin:0 auto; padding:20px; color:#0f172a">
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#0F1B3A;border-radius:8px;padding:20px 24px;color:#fff">
    <tr><td>
      <div style="font-size:11px;letter-spacing:2px;color:#F4C86D;text-transform:uppercase;font-weight:600">Daily Alert Digest</div>
      <h1 style="margin:6px 0 0;font-size:22px;font-weight:700">{BRAND}</h1>
    </td></tr>
  </table>
  <p style="margin-top:20px">Hello {digest['name']},</p>
  <p><b>{len(digest['breaches'])} of {digest['total_views_checked']}</b> pinned view(s) are currently above their alert threshold:</p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#fff;border:1px solid #e7e5e4;border-radius:6px;margin-top:12px">
    {rows_html}
  </table>
  <p style="font-size:13px;color:#6b7280;margin-top:20px">Open the admin dashboard to drill in and act:</p>
  <p style="text-align:center;margin:14px 0 6px">
    <a href="#" style="background:#0F1B3A;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;display:inline-block">Open Dashboard</a>
  </p>
  <p style="font-size:12px;color:#9ca3af">You're receiving this because you pinned these views and set an alert threshold. Adjust the threshold on the Reports page (Saved Views strip).</p>
  {FOOTER_HTML}
</body>
</html>
"""
    return subject, html


# ---------------------------------------------------------------------
# Persistence + sending
# ---------------------------------------------------------------------
async def run_alert_digest() -> dict:
    """Compute digests for every user and email those with breaches.

    Returns a summary dict for logging/auditing.
    """
    users = await db.users.find({"active": {"$ne": False}}, {"_id": 0}).to_list(500)
    sent = 0
    skipped_no_breach = 0
    mocked = 0
    errors: list[str] = []
    per_user: list[dict] = []

    for u in users:
        digest = await compute_user_digest(u)
        per_user.append({
            "user_id": digest["user_id"],
            "email": digest["email"],
            "breach_count": len(digest["breaches"]),
        })
        if not digest["breaches"]:
            skipped_no_breach += 1
            continue

        # Persist history
        record = {
            "id": new_id(),
            "user_id": digest["user_id"],
            "email": digest["email"],
            "breaches": digest["breaches"],
            "total_views_checked": digest["total_views_checked"],
            "created_at": utcnow_iso(),
        }
        await db.alert_digests.insert_one(record)

        subject, html = render_digest_email(digest)
        try:
            res = await send_email(digest["email"], subject, html)
            if res.get("status") == "sent":
                sent += 1
            else:
                mocked += 1
            await db.alert_digests.update_one(
                {"id": record["id"]},
                {"$set": {"delivery": res}},
            )
        except Exception as exc:
            errors.append(f"{digest['email']}: {exc}")
            log.exception("[alerts] send failed")

    summary = {
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "users_scanned": len(users),
        "emails_sent": sent,
        "emails_mocked": mocked,
        "no_breach": skipped_no_breach,
        "errors": errors,
        "email_configured": email_configured(),
        "per_user": per_user,
    }
    log.info("[alerts] digest run: %s", summary)
    return summary


def run_alert_digest_sync() -> None:
    """Synchronous wrapper for APScheduler."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_alert_digest())
        loop.close()
    except Exception:
        log.exception("[scheduler] alert digest job crashed")


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------
@router.get("/alerts/preview")
async def preview_my_digest(user: dict = Depends(get_current_user)):
    """Preview what your alert digest looks like RIGHT NOW (does not send)."""
    digest = await compute_user_digest(user)
    return digest


@router.get("/alerts/history")
async def digest_history(user: dict = Depends(get_current_user)):
    """Last 30 digests we generated for you (only records with breaches are stored)."""
    rows = await db.alert_digests.find(
        {"user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(30).to_list(30)
    return rows


@router.post("/alerts/run-now")
async def run_now(_: dict = Depends(require_admin)):
    """Admin-only: trigger the digest job immediately for all users."""
    return await run_alert_digest()
