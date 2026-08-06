import os
import logging
from pathlib import Path
import mimetypes

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/home/fp/private/pawn_django/upload/files"))


def init_storage() -> str | None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return str(UPLOAD_DIR)


def _safe_path(path: str) -> Path:
    key = str(path or "").lstrip("/")
    full = (UPLOAD_DIR / key).resolve()
    root = UPLOAD_DIR.resolve()

    if not str(full).startswith(str(root)):
        raise RuntimeError("Invalid storage path")

    return full


def put_object(path: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    init_storage()
    full = _safe_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)

    return {
        "path": path,
        "size": len(data),
        "etag": "",
        "content_type": content_type,
    }


def get_object(path: str) -> tuple[bytes, str]:
    full = _safe_path(path)

    if not full.exists():
        raise FileNotFoundError(f"Object not found: {path}")

    content_type = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
    return full.read_bytes(), content_type


def delete_object(path: str) -> bool:
    full = _safe_path(path)

    if full.exists():
        full.unlink()
        return True

    return False
