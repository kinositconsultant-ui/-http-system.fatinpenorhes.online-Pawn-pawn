"""WebSocket endpoint for live Business Dashboard updates.

Client connects to /api/ws/dashboard. Auth is drawn from the `access_token`
cookie (same JWT the REST API uses) OR a `?token=` query param fallback for
environments that strip cookies from the WS handshake. On any dashboard-
relevant mutation, the server pushes `{"kind": "...", "ts": "..."}` and the
frontend refetches the dashboard aggregate.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from auth import decode_token
from deps import db
from realtime import manager

router = APIRouter(tags=["realtime"])
logger = logging.getLogger("fatin.ws")


async def _authenticate(ws: WebSocket, token_qs: str | None) -> dict | None:
    """Validate JWT from cookie or query string. Return user dict or None."""
    token = ws.cookies.get("access_token") or token_qs
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user = await db.users.find_one(
            {"id": payload["sub"]}, {"_id": 0, "password_hash": 0}
        )
        return user
    except Exception as e:  # noqa: BLE001
        logger.debug(f"ws auth failed: {e}")
        return None


@router.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket, token: str | None = Query(default=None)):
    user = await _authenticate(ws, token)
    if not user:
        # 1008 = policy violation (auth failed)
        await ws.close(code=1008)
        return
    await manager.connect(ws)
    try:
        await ws.send_json({
            "kind": "connected",
            "payload": {"user_id": user.get("id")},
        })
        while True:
            # We don't expect client messages, but keep the socket alive by
            # awaiting anything (ping frames, empty text). Break on disconnect.
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        logger.debug(f"ws loop error: {e}")
    finally:
        await manager.disconnect(ws)
