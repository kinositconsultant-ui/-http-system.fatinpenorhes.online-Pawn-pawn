"""WhatsApp Cloud API (Meta direct) sender — with safe mock fallback when creds absent."""
import os
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def is_configured(settings: dict | None = None) -> bool:
    token = (settings or {}).get("whatsapp_token") or os.environ.get("WHATSAPP_TOKEN")
    phone_id = (settings or {}).get("whatsapp_phone_id") or os.environ.get("WHATSAPP_PHONE_ID")
    return bool(token and phone_id)


def _clean_phone(p: str) -> str:
    return "".join(ch for ch in (p or "") if ch.isdigit())


async def send_template(
    to_phone: str,
    template_name: str,
    language_code: str,
    parameters: list[str],
    settings: dict | None = None,
) -> dict:
    """Send a templated WhatsApp message. Returns {"status": "sent"|"mocked"|"error", ...}."""
    sett = settings or {}
    token = sett.get("whatsapp_token") or os.environ.get("WHATSAPP_TOKEN") or ""
    phone_id = sett.get("whatsapp_phone_id") or os.environ.get("WHATSAPP_PHONE_ID") or ""
    api_version = os.environ.get("WHATSAPP_API_VERSION", "v20.0")
    to_clean = _clean_phone(to_phone)

    payload = {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)} for p in parameters],
                }
            ],
        },
    }

    if not (token and phone_id and to_clean):
        # Mock send — record and return
        logger.info(
            "[WhatsApp MOCK] to=%s template=%s params=%s",
            to_clean,
            template_name,
            parameters,
        )
        return {
            "status": "mocked",
            "to": to_clean,
            "template": template_name,
            "parameters": parameters,
            "language": language_code,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "note": "WhatsApp not configured — message logged only. Add token + phone id in Settings.",
        }

    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text}
        if resp.status_code in (200, 201):
            return {
                "status": "sent",
                "to": to_clean,
                "template": template_name,
                "parameters": parameters,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "meta_message_id": (data.get("messages") or [{}])[0].get("id"),
                "raw": data,
            }
        return {
            "status": "error",
            "to": to_clean,
            "template": template_name,
            "parameters": parameters,
            "error": data,
            "http_status": resp.status_code,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("WhatsApp send failed")
        return {
            "status": "error",
            "to": to_clean,
            "template": template_name,
            "parameters": parameters,
            "error": str(e),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }


async def send_text(to_phone: str, body: str, settings: dict | None = None) -> dict:
    """Send a free-form text WhatsApp message (test/debug only).

    Note: Meta restricts free-form text to the 24-hour service window; outside that,
    only approved templates work. Use this for connectivity tests with your own number.
    """
    sett = settings or {}
    token = sett.get("whatsapp_token") or os.environ.get("WHATSAPP_TOKEN") or ""
    phone_id = sett.get("whatsapp_phone_id") or os.environ.get("WHATSAPP_PHONE_ID") or ""
    api_version = os.environ.get("WHATSAPP_API_VERSION", "v22.0")
    to_clean = _clean_phone(to_phone)

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_clean,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }

    if not (token and phone_id and to_clean):
        logger.info("[WhatsApp MOCK send_text] to=%s body=%r", to_clean, body[:80])
        return {
            "status": "mocked",
            "to": to_clean,
            "body": body,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "note": "WhatsApp not configured — message logged only.",
        }

    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text}
        if resp.status_code in (200, 201):
            return {
                "status": "sent",
                "to": to_clean,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "meta_message_id": (data.get("messages") or [{}])[0].get("id"),
                "raw": data,
            }
        return {
            "status": "error",
            "to": to_clean,
            "error": data,
            "http_status": resp.status_code,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("WhatsApp send_text failed")
        return {
            "status": "error",
            "to": to_clean,
            "error": str(e),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
