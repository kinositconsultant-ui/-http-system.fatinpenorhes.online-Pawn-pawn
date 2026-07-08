"""Iteration 35 — Pawn Item photo thumbnails.

Verifies:
- Every item kind (car, motorcycle, electronic, pezadu) accepts a thumbnail_url
  on POST, round-trips it on GET, and persists it on PUT.
- ItemIn models still reject missing required fields (regression).
"""
from __future__ import annotations

import io
import os
import uuid

import pytest
import requests
from PIL import Image

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login() -> requests.Session:
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@fatinpenhores.tl", "password": "admin123"},
    )
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def api_sess():
    return _login()


@pytest.fixture(scope="module")
def uploaded_photo(api_sess):
    im = Image.new("RGB", (1200, 800), color=(200, 150, 100))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    r = api_sess.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("item.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert r.status_code == 200
    b = r.json()
    assert b["thumbnail_storage_path"], "upload should generate a thumbnail"
    return b  # {storage_path, thumbnail_storage_path, url, thumbnail_url, ...}


@pytest.fixture
def created_items():
    ids: list[tuple[str, str]] = []
    yield ids
    if not ids:
        return
    s = _login()
    for kind, iid in ids:
        s.delete(f"{BASE_URL}/api/items/{kind}/{iid}")


@pytest.mark.parametrize("kind,extra", [
    ("car",        {"name": "Toyota Hilux 2020", "brand": "Toyota", "model": "Hilux"}),
    ("motorcycle", {"brand": "Honda", "model": "CBR150"}),
    ("electronic", {"category": "Phone", "brand": "Apple", "model": "iPhone 12"}),
    ("pezadu",     {"category": "forklift", "brand": "Komatsu", "model": "FD25T"}),
])
def test_item_persists_thumbnail_url(api_sess, uploaded_photo, created_items, kind, extra):
    payload = {
        **extra,
        "market_value": 5000,
        "photo_url": uploaded_photo["storage_path"],
        "thumbnail_url": uploaded_photo["thumbnail_storage_path"],
    }
    r = api_sess.post(f"{BASE_URL}/api/items/{kind}", json=payload)
    assert r.status_code == 200, r.text
    item = r.json()
    created_items.append((kind, item["id"]))
    assert item["thumbnail_url"] == uploaded_photo["thumbnail_storage_path"]
    assert item["photo_url"] == uploaded_photo["storage_path"]

    # Round-trip: list + get both echo thumbnail_url
    listing = api_sess.get(f"{BASE_URL}/api/items/{kind}").json()
    mine = next(x for x in listing if x["id"] == item["id"])
    assert mine["thumbnail_url"] == uploaded_photo["thumbnail_storage_path"]

    got = api_sess.get(f"{BASE_URL}/api/items/{kind}/{item['id']}").json()
    assert got["thumbnail_url"] == uploaded_photo["thumbnail_storage_path"]


def test_item_put_updates_thumbnail_when_photo_changes(api_sess, uploaded_photo, created_items):
    # Create with initial photo
    tag = uuid.uuid4().hex[:6]
    r = api_sess.post(f"{BASE_URL}/api/items/car", json={
        "name": f"Test {tag}", "brand": "Toyota", "model": "Hilux",
        "market_value": 5000,
        "photo_url": uploaded_photo["storage_path"],
        "thumbnail_url": uploaded_photo["thumbnail_storage_path"],
    })
    cid = r.json()["id"]
    created_items.append(("car", cid))

    # Upload a fresh image and PUT
    im = Image.new("RGB", (800, 800), color=(100, 200, 100))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    up2 = api_sess.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("new.jpg", buf.getvalue(), "image/jpeg")},
    ).json()

    r2 = api_sess.put(f"{BASE_URL}/api/items/car/{cid}", json={
        "name": f"Test {tag}", "brand": "Toyota", "model": "Hilux",
        "market_value": 5500,
        "photo_url": up2["storage_path"],
        "thumbnail_url": up2["thumbnail_storage_path"],
    })
    assert r2.status_code == 200
    assert r2.json()["photo_url"] == up2["storage_path"]
    assert r2.json()["thumbnail_url"] == up2["thumbnail_storage_path"]


def test_item_without_photo_has_empty_thumbnail(api_sess, created_items):
    r = api_sess.post(f"{BASE_URL}/api/items/car", json={
        "name": "No photo item", "brand": "Ford", "model": "Ranger",
        "market_value": 4000,
    })
    assert r.status_code == 200
    created_items.append(("car", r.json()["id"]))
    assert r.json()["thumbnail_url"] == ""
    assert r.json()["photo_url"] == ""


def test_item_kind_validation_still_enforced(api_sess):
    r = api_sess.post(f"{BASE_URL}/api/items/car", json={"model": "no brand"})
    assert r.status_code == 422
