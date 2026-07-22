"""Email service — Resend SDK wrapper with graceful mocked fallback.

Falls back to "mocked" (logs body, does not send) when RESEND_API_KEY is empty,
matching the WhatsApp integration's UX so the app remains fully functional
before the admin provides a key.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import resend

logger = logging.getLogger(__name__)

BRAND = "Fatin Penhores"
FOOTER_HTML = (
    '<hr style="border:0;border-top:1px solid #e7e5e4;margin:24px 0" />'
    '<p style="color:#6b7280;font-size:12px;line-height:1.5;margin:0">'
    'Fatin Penhores Unipessoal, Lda · Caicoli, Dili, Timor-Leste · '
    'WhatsApp: +670 78372678 · fatinpenhores@gmail.com'
    '</p>'
)


def is_configured() -> bool:
    """Return True if a Resend API key + sender email are both set."""
    return bool(os.environ.get("RESEND_API_KEY", "").strip()) and bool(
        os.environ.get("SENDER_EMAIL", "").strip()
    )


def _mock_result(to: str, subject: str, reason: str) -> dict:
    logger.warning("[email] MOCKED — %s → to=%s subject=%s", reason, to, subject)
    return {
        "status": "mocked",
        "to": to,
        "subject": subject,
        "note": f"Email not sent — {reason}",
    }


async def send_email(
    to: str,
    subject: str,
    html: str,
    reply_to: Optional[str] = None,
    attachments: Optional[list[dict]] = None,
) -> dict:
    """Send an HTML email via Resend. Returns dict with status + id (or mocked).

    Args:
        attachments: optional list of `{"filename": str, "content": bytes}`.
            The bytes are base64-encoded and passed to Resend as attachments.
    """
    if not to or "@" not in to:
        return _mock_result(to, subject, "invalid recipient")
    if not is_configured():
        return _mock_result(to, subject, "RESEND_API_KEY not configured")

    resend.api_key = os.environ["RESEND_API_KEY"]
    params: dict = {
        "from": os.environ["SENDER_EMAIL"],
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if reply_to:
        params["reply_to"] = reply_to
    if attachments:
        import base64  # noqa: PLC0415
        params["attachments"] = [
            {
                "filename": a["filename"],
                "content": base64.b64encode(a["content"]).decode("ascii"),
            }
            for a in attachments
            if a.get("content")
        ]
    try:
        # Resend SDK is sync — offload to thread so FastAPI event loop stays free
        res = await asyncio.to_thread(resend.Emails.send, params)
        return {
            "status": "sent",
            "id": res.get("id") if isinstance(res, dict) else None,
            "to": to,
            "subject": subject,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("[email] send failed: %s", exc)
        return {"status": "error", "error": str(exc), "to": to, "subject": subject}


# ---------------------------------------------------------------------
# Ready-made templates
# ---------------------------------------------------------------------
def render_overdue_reminder(
    client_name: str,
    contract_number: str,
    days_overdue: int,
    total_due: float,
    per_month_interest: float,
    months: int,
    next_month_date: str,
    days_left: int,
) -> tuple[str, str]:
    """Return (subject, html) for the overdue-payment reminder email.

    Mirrors the WhatsApp body (Rule A math) so both channels stay consistent.
    """
    subject = f"{BRAND} — Overdue Notice: {contract_number}"
    html = f"""
<!doctype html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width:600px; margin:0 auto; padding:24px; color:#0f172a">
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#0F1B3A;border-radius:8px;padding:20px 24px;color:#fff">
    <tr><td>
      <div style="font-size:12px;letter-spacing:2px;color:#F4C86D;text-transform:uppercase;font-weight:600">Overdue Notice</div>
      <h1 style="margin:6px 0 0;font-size:22px;font-weight:700">{BRAND}</h1>
    </td></tr>
  </table>
  <p style="margin-top:24px">Hello <b>{client_name}</b>,</p>
  <p>Contract <b>{contract_number}</b> is <b>{days_overdue} days overdue</b>.</p>
  <table role="presentation" cellpadding="8" cellspacing="0" style="width:100%;background:#f5f5f4;border-radius:6px;font-size:14px">
    <tr><td style="color:#57534e">Billing months</td><td style="text-align:right"><b>{months}</b></td></tr>
    <tr><td style="color:#57534e">Interest / month</td><td style="text-align:right"><b>${per_month_interest:,.2f}</b></td></tr>
    <tr><td style="color:#57534e;border-top:1px solid #d6d3d1">Total owed today</td><td style="text-align:right;border-top:1px solid #d6d3d1;font-size:18px;color:#0F1B3A"><b>${total_due:,.2f}</b></td></tr>
  </table>
  <p style="background:#fef3c7;border-left:3px solid #F4C86D;padding:12px;margin:20px 0;font-size:14px">
    On <b>{next_month_date}</b>, one more month of interest kicks in.<br/>
    Please pay within <b>{days_left} more days</b> to avoid auction.
  </p>
  <p>Contact us via WhatsApp <b>+670 78372678</b> to discuss a payment plan.</p>
  {FOOTER_HTML}
</body>
</html>
"""
    return subject, html


def render_password_reset(reset_link: str, expires_min: int = 15) -> tuple[str, str]:
    subject = f"{BRAND} — Reset your password"
    html = f"""
<!doctype html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width:600px; margin:0 auto; padding:24px; color:#0f172a">
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#0F1B3A;border-radius:8px;padding:20px 24px;color:#fff">
    <tr><td>
      <div style="font-size:12px;letter-spacing:2px;color:#F4C86D;text-transform:uppercase;font-weight:600">Password Reset</div>
      <h1 style="margin:6px 0 0;font-size:22px;font-weight:700">{BRAND}</h1>
    </td></tr>
  </table>
  <p style="margin-top:24px">We received a request to reset your admin console password.</p>
  <p>Click the button below to choose a new password. This link expires in <b>{expires_min} minutes</b> and can only be used once.</p>
  <p style="text-align:center;margin:32px 0">
    <a href="{reset_link}" style="background:#0F1B3A;color:#fff;padding:14px 28px;border-radius:6px;text-decoration:none;font-weight:600;display:inline-block">Reset Password</a>
  </p>
  <p style="font-size:12px;color:#6b7280">Or copy & paste this URL into your browser:<br/>
  <span style="word-break:break-all">{reset_link}</span></p>
  <p style="font-size:13px;color:#6b7280">If you didn't request this, ignore this email — your password stays unchanged.</p>
  {FOOTER_HTML}
</body>
</html>
"""
    return subject, html
