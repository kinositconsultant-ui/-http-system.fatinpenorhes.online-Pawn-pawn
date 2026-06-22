"""Emergent object storage client for Fatin Penhores."""
import os
import logging
import requests

logger = logging.getLogger(__name__)

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"

_storage_key: str | None = None


def _emergent_key() -> str:
    return os.environ["EMERGENT_LLM_KEY"]


def init_storage() -> str | None:
    """Initialize storage session. Returns key or None on failure."""
    global _storage_key
    if _storage_key:
        return _storage_key
    try:
        resp = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": _emergent_key()},
            timeout=30,
        )
        resp.raise_for_status()
        _storage_key = resp.json()["storage_key"]
        logger.info("Object storage initialized")
        return _storage_key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        _storage_key = None
        return None


def _ensure_key() -> str:
    key = init_storage()
    if not key:
        raise RuntimeError("Object storage not available")
    return key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload bytes. Returns {"path": ..., "size": ..., "etag": ...}."""
    key = _ensure_key()
    try:
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
        if resp.status_code == 403:
            # try once more with fresh key
            global _storage_key
            _storage_key = None
            key = _ensure_key()
            resp = requests.put(
                f"{STORAGE_URL}/objects/{path}",
                headers={"X-Storage-Key": key, "Content-Type": content_type},
                data=data,
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"put_object failed: {e}")
        raise


def get_object(path: str) -> tuple[bytes, str]:
    """Download bytes. Returns (content, content_type)."""
    key = _ensure_key()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    if resp.status_code == 403:
        global _storage_key
        _storage_key = None
        key = _ensure_key()
        resp = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
