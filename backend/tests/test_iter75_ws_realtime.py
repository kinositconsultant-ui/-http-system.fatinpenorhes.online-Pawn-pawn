"""iter75 — WebSocket real-time dashboard broadcaster.

Verifies:
 * Unauthenticated WS handshake is rejected.
 * Authenticated WS receives the `connected` frame.
 * Creating an expense triggers an `expense.created` broadcast that reaches
   the connected client within a few seconds.

Uses `asyncio.run` inside sync pytest functions to avoid needing
`pytest-asyncio` (not installed in this project).
"""
from __future__ import annotations

import asyncio
import json
import os

import pytest
import requests
import websockets

BASE = os.environ.get(
    "TEST_BASE_URL",
    "https://pawnly-pro.preview.emergentagent.com",
).rstrip("/")
WS_BASE = BASE.replace("https://", "wss://").replace("http://", "ws://")


def _login_token() -> str:
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": "admin@fatinpenhores.tl", "password": "admin123"},
        timeout=10,
    )
    r.raise_for_status()
    cookie = r.cookies.get("access_token")
    assert cookie, "login did not return access_token cookie"
    return cookie


async def _unauth() -> str:
    try:
        async with websockets.connect(f"{WS_BASE}/api/ws/dashboard") as ws:
            await asyncio.wait_for(ws.recv(), timeout=3)
    except Exception as e:  # noqa: BLE001
        return type(e).__name__
    return "OPENED"


def test_ws_rejects_unauth():
    outcome = asyncio.run(_unauth())
    assert outcome != "OPENED", "WS should reject unauthenticated handshake"


async def _push_flow(token: str) -> dict:
    url = f"{WS_BASE}/api/ws/dashboard?token={token}"
    async with websockets.connect(url) as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert first["kind"] == "connected"
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.post(
            f"{BASE}/api/expenses",
            json={
                "category": "Other",
                "amount": 0.99,
                "date": "2026-02-06",
                "description": "iter75 ws smoketest",
            },
            headers=headers,
            timeout=10,
        )
        assert r.status_code == 200, r.text
        for _ in range(5):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if msg.get("kind") == "expense.created":
                return msg
    raise AssertionError("did not receive expense.created")


def test_ws_receives_expense_event():
    token = _login_token()
    msg = asyncio.run(_push_flow(token))
    assert msg["payload"]["amount"] == 0.99
    assert msg["payload"]["category"] == "Other"
