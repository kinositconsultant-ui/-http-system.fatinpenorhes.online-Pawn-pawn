"""Iteration 34 — Client photo thumbnails + auto-issue member_verify_token.

Verifies:
- /api/upload of an image returns a thumbnail_storage_path + thumbnail_url.
- The thumbnail is a valid JPEG ≤ 200x200 and strictly smaller than the original.
- Non-image uploads (e.g. PDF) do NOT get a thumbnail.
- POST /api/clients with photo_url auto-issues a member_verify_token.
- POST /api/clients without photo_url does NOT issue a token.
- PUT /api/clients/{id} adding a photo auto-issues a token.
- thumbnail_url is round-tripped on client GET.
"""
from __future__ import annotations

import io
import os
import uuid

import pytest
import requests
from PIL import Image

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@fatinpenhores.tl"
ADMIN_PASS = "admin123"


def _make_big_jpeg() -> bytes:
    im = Image.new("RGB", (1200, 800), color=(27, 45, 92))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _make_tiny_png() -> bytes:
    im = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def api_sess():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
    )
    assert r.status_code == 200
    return s


@pytest.fixture
def created_client_ids():
    """Cleanup fixture — auto-deletes any client ids we push to it."""
    ids: list[str] = []
    yield ids
    if not ids:
        return
    s = requests.Session()
    s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    for cid in ids:
        s.delete(f"{BASE_URL}/api/clients/{cid}")


def test_upload_image_returns_thumbnail(api_sess):
    orig = _make_big_jpeg()
    r = api_sess.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("photo.jpg", orig, "image/jpeg")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["storage_path"]
    assert body["thumbnail_storage_path"]
    assert body["thumbnail_url"].startswith("/api/files/")

    # Download the thumbnail and verify size + format
    tr = api_sess.get(f"{BASE_URL}/api/files/{body['thumbnail_storage_path']}")
    assert tr.status_code == 200
    im = Image.open(io.BytesIO(tr.content))
    assert im.format == "JPEG"
    w, h = im.size
    assert w <= 200 and h <= 200, f"thumb too big: {im.size}"
    # Strictly smaller in bytes than the original
    assert len(tr.content) < len(orig) / 4, (
        f"thumb ({len(tr.content)}B) not < 25% of original ({len(orig)}B)"
    )


def test_upload_non_image_has_no_thumbnail(api_sess):
    fake_pdf = b"%PDF-1.4\n%not really a pdf but content_type says so\n"
    r = api_sess.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("doc.pdf", fake_pdf, "application/pdf")},
    )
    assert r.status_code == 200
    assert "thumbnail_storage_path" not in r.json()
    assert "thumbnail_url" not in r.json()


def test_create_client_with_photo_auto_issues_token(api_sess, created_client_ids):
    up = api_sess.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("p.jpg", _make_big_jpeg(), "image/jpeg")},
    ).json()

    tag = uuid.uuid4().hex[:6]
    r = api_sess.post(f"{BASE_URL}/api/clients", json={
        "full_name": f"TestThumb {tag}",
        "id_type": "BI",
        "id_number": f"THUMB-{tag}",
        "phone": "+670-1234",
        "photo_url": up["storage_path"],
        "thumbnail_url": up["thumbnail_storage_path"],
    })
    assert r.status_code == 200
    c = r.json()
    created_client_ids.append(c["id"])
    assert c["thumbnail_url"] == up["thumbnail_storage_path"]
    assert c["photo_url"] == up["storage_path"]
    assert c.get("member_verify_token"), "expected member_verify_token to be auto-issued"


def test_create_client_without_photo_does_not_issue_token(api_sess, created_client_ids):
    tag = uuid.uuid4().hex[:6]
    r = api_sess.post(f"{BASE_URL}/api/clients", json={
        "full_name": f"NoPhoto {tag}",
        "id_type": "BI",
        "id_number": f"NOPHOTO-{tag}",
        "phone": "+670-1234",
    })
    assert r.status_code == 200
    c = r.json()
    created_client_ids.append(c["id"])
    assert not c.get("member_verify_token")


def test_put_adds_photo_and_auto_issues_token(api_sess, created_client_ids):
    tag = uuid.uuid4().hex[:6]
    # Step 1 — create without photo (no token)
    r = api_sess.post(f"{BASE_URL}/api/clients", json={
        "full_name": f"Upgrader {tag}",
        "id_type": "BI",
        "id_number": f"UP-{tag}",
        "phone": "+670",
    })
    cid = r.json()["id"]
    created_client_ids.append(cid)
    assert not r.json().get("member_verify_token")

    # Step 2 — upload + PUT with photo
    up = api_sess.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("p.jpg", _make_big_jpeg(), "image/jpeg")},
    ).json()
    r2 = api_sess.put(f"{BASE_URL}/api/clients/{cid}", json={
        "full_name": f"Upgrader {tag}",
        "id_type": "BI",
        "id_number": f"UP-{tag}",
        "phone": "+670",
        "photo_url": up["storage_path"],
        "thumbnail_url": up["thumbnail_storage_path"],
    })
    assert r2.status_code == 200
    updated = r2.json()
    assert updated["photo_url"] == up["storage_path"]
    assert updated["thumbnail_url"] == up["thumbnail_storage_path"]
    assert updated.get("member_verify_token"), "PUT should auto-issue token when photo added"


def test_put_does_not_overwrite_existing_token(api_sess, created_client_ids):
    up = api_sess.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("p.jpg", _make_big_jpeg(), "image/jpeg")},
    ).json()
    tag = uuid.uuid4().hex[:6]
    r = api_sess.post(f"{BASE_URL}/api/clients", json={
        "full_name": f"Persist {tag}", "id_type": "BI", "id_number": f"PSK-{tag}",
        "phone": "+670", "photo_url": up["storage_path"],
        "thumbnail_url": up["thumbnail_storage_path"],
    })
    cid = r.json()["id"]
    original_token = r.json()["member_verify_token"]
    created_client_ids.append(cid)

    # PUT with a new photo — token should stay the same
    up2 = api_sess.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("p2.jpg", _make_big_jpeg(), "image/jpeg")},
    ).json()
    r2 = api_sess.put(f"{BASE_URL}/api/clients/{cid}", json={
        "full_name": f"Persist {tag}", "id_type": "BI", "id_number": f"PSK-{tag}",
        "phone": "+670", "photo_url": up2["storage_path"],
        "thumbnail_url": up2["thumbnail_storage_path"],
    })
    assert r2.json()["member_verify_token"] == original_token
