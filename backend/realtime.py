"""Real-time WebSocket broadcaster for the Business Dashboard.

A tiny in-memory pub/sub. When any mutation happens (payment, contract,
auction, expense, funding, inspection reimburse), backend code calls
`notify(kind, payload)` and every subscribed WebSocket receives a JSON
frame. The frontend uses this as a signal to refetch `/business/dashboard`
immediately instead of waiting for the 60-second poll.

Failures are swallowed — this is a "nice-to-have" push channel, never a
source of truth. The polling fallback stays in place.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger("fatin.realtime")


class ConnectionManager:
    def __init__(self) -> None:
        self._active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._active.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._active.discard(ws)

    async def broadcast(self, message: dict) -> None:
        if not self._active:
            return
        text = json.dumps(message)
        dead: list[WebSocket] = []
        # Copy set to iterate safely without holding the lock during send
        async with self._lock:
            targets = list(self._active)
        for ws in targets:
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._active.discard(ws)

    @property
    def active_count(self) -> int:
        return len(self._active)


manager = ConnectionManager()


def notify(kind: str, payload: dict | None = None) -> None:
    """Fire-and-forget broadcast. Never awaits, never raises."""
    try:
        loop = asyncio.get_event_loop()
        message = {
            "kind": kind,
            "payload": payload or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        loop.create_task(manager.broadcast(message))
    except Exception as e:  # noqa: BLE001
        logger.debug(f"notify swallowed: {e}")


__all__ = ["manager", "notify"]
