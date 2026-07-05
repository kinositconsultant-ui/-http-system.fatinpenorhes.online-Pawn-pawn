"""Shared dependencies + helpers for all API routers.

Centralises DB access, auth guards, and common utilities so that router
modules don't reach back into server.py. Import from here in every router.
"""
from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta
from typing import List, Optional

from fastapi import Request, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorClient

from auth import decode_token

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
_mongo_url = os.environ["MONGO_URL"]
_client = AsyncIOMotorClient(_mongo_url)
db = _client[os.environ["DB_NAME"]]

logger = logging.getLogger("fatin")


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def months_billed(start: date, payment_date: date) -> int:
    """Rule A — Strict calendar month + 1 grace day. Min 1.

    - The first monthly billing period is ALWAYS charged.
    - Payment on the monthly anniversary of the start date → same month.
    - One day past the anniversary → new full month begins.

    Shared with `server._months_billed` so backend + reminders always agree
    on the money math.
    """
    if payment_date <= start:
        return 1
    months = 1
    anniv = start + relativedelta(months=1)
    while payment_date > anniv:
        months += 1
        anniv = anniv + relativedelta(months=1)
    return months


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
# Module catalog — canonical list of modules a user can be granted access to.
# Keep in sync with the frontend AdminLayout sidebar and MODULE_ROUTES map.
ALL_MODULES = [
    "dashboard",
    "clients",
    "items",
    "contracts",
    "payments",
    "auctions",
    "reports",
    "finance",
    "users",
    "settings",
    "audit_log",
]

# Default module sets per role (admin always gets everything).
ROLE_DEFAULT_MODULES = {
    "admin": ALL_MODULES,
    "staff": ["dashboard", "clients", "items", "contracts", "payments", "auctions", "reports"],
    "cashier": ["dashboard", "payments"],
}

# Pawn item kind -> Mongo collection name
COLLECTION_MAP = {
    "car": "cars",
    "motorcycle": "motorcycles",
    "electronic": "electronics",
    "pezadu": "pezadus",
}


# ---------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------
async def get_current_user(request: Request) -> dict:
    """Extract user from JWT cookie or Bearer token."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_module(module: str):
    """Block API access if the user's `allowed_modules` doesn't include this module.

    Admins bypass. Non-admins must have the module explicitly listed."""
    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") == "admin":
            return user
        allowed = user.get("allowed_modules") or ROLE_DEFAULT_MODULES.get(user.get("role"), [])
        if module not in allowed:
            raise HTTPException(status_code=403, detail=f"You don't have access to the {module} module")
        return user
    return _dep


def require_roles(*allowed: str):
    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires role in {allowed}")
        return user
    return _dep


# Shortcut used across write endpoints
require_not_cashier = require_roles("admin", "staff")


# ---------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------
async def write_audit(
    actor: dict,
    action: str,
    resource: str,
    resource_id: Optional[str] = None,
    payload: Optional[dict] = None,
):
    """Best-effort audit trail — never blocks primary operation."""
    try:
        await db.audit_log.insert_one({
            "id": new_id(),
            "actor_id": actor.get("id"),
            "actor_email": actor.get("email"),
            "actor_role": actor.get("role"),
            "action": action,
            "resource": resource,
            "resource_id": resource_id or "",
            "payload": payload or {},
            "created_at": utcnow_iso(),
        })
    except Exception as e:
        logger.warning(f"audit log failed: {e}")


__all__ = [
    "db",
    "logger",
    "utcnow_iso",
    "new_id",
    "ALL_MODULES",
    "ROLE_DEFAULT_MODULES",
    "COLLECTION_MAP",
    "get_current_user",
    "require_admin",
    "require_module",
    "require_roles",
    "require_not_cashier",
    "write_audit",
]
