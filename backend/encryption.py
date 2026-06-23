"""Symmetric token encryption for sensitive credentials stored in MongoDB.

We use Fernet (cryptography library) keyed off WHATSAPP_ENCRYPTION_KEY in .env.
If the key is missing, the helpers fall back to no-op so dev / first-run keep working,
but a warning is logged so admins know stored creds are NOT encrypted.
"""
from __future__ import annotations

import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_key = os.environ.get("WHATSAPP_ENCRYPTION_KEY", "").strip()
_fernet: Fernet | None = None
if _key:
    try:
        _fernet = Fernet(_key.encode())
    except Exception:  # noqa: BLE001
        logger.error("WHATSAPP_ENCRYPTION_KEY is invalid — token storage will be plaintext.")
        _fernet = None
else:
    logger.warning("WHATSAPP_ENCRYPTION_KEY not set — token storage will be plaintext.")


def encrypt_token(plain: str) -> str:
    if not plain:
        return ""
    if not _fernet:
        return plain
    return _fernet.encrypt(plain.encode()).decode()


def decrypt_token(stored: str) -> str:
    if not stored:
        return ""
    if not _fernet:
        return stored
    try:
        return _fernet.decrypt(stored.encode()).decode()
    except InvalidToken:
        # Stored as plaintext previously — return as-is so we don't lose access
        return stored
    except Exception:  # noqa: BLE001
        logger.exception("Failed to decrypt token")
        return ""


def mask_token(stored: str) -> str:
    """Return a UI-safe masked preview of the encrypted/plaintext token."""
    plain = decrypt_token(stored)
    if not plain:
        return ""
    if len(plain) <= 8:
        return "•" * len(plain)
    return f"{plain[:4]}••••{plain[-4:]}"


def is_configured(stored: str) -> bool:
    return bool(decrypt_token(stored))
