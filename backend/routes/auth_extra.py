"""Password reset flow — self-service email link + admin manual reset.

Uses Resend (email_svc) with graceful mocked fallback so the flow is still
observable in logs before the admin provides an API key.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from deps import db, new_id, utcnow_iso, require_admin, write_audit
from auth import hash_password
import email_svc

router = APIRouter()

# Reset token config
RESET_TOKEN_TTL_MIN = 15


def _public_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "").rstrip("/") or ""


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=16)
    new_password: str = Field(min_length=8, max_length=200)


class AdminResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordIn, request: Request):
    """Request a password reset email.

    We ALWAYS return 200 with a generic message so an attacker can't enumerate
    valid emails. When the email exists, we mint a single-use token, save it,
    and fire the reset email via Resend (mocked when no API key).
    """
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    generic = {"ok": True, "message": "If an account exists for that email, a reset link was sent."}
    if not user:
        return generic

    # Invalidate any earlier tokens for this user (defense in depth)
    await db.password_reset_tokens.delete_many({"user_id": user["id"], "used_at": None})

    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=RESET_TOKEN_TTL_MIN)
    await db.password_reset_tokens.insert_one({
        "id": new_id(),
        "user_id": user["id"],
        "email": email,
        "token": token,
        "expires_at": expires_at.isoformat(),
        "created_at": now.isoformat(),
        "requester_ip": request.client.host if request.client else None,
        "used_at": None,
    })

    reset_link = f"{_public_base_url()}/reset-password?token={token}"
    subject, html = email_svc.render_password_reset(reset_link, expires_min=RESET_TOKEN_TTL_MIN)
    result = await email_svc.send_email(email, subject, html)

    await db.audit_log.insert_one({
        "id": new_id(),
        "actor_id": user["id"],
        "actor_email": email,
        "action": "forgot_password_request",
        "resource": "user",
        "resource_id": user["id"],
        "details": {"email_result": result.get("status")},
        "created_at": utcnow_iso(),
    })
    return generic


@router.get("/auth/reset-token-info")
async def reset_token_info(token: str):
    """Public endpoint used by the /reset-password page to validate the token
    BEFORE the user types a new password. Returns email masked."""
    doc = await db.password_reset_tokens.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    if doc.get("used_at"):
        raise HTTPException(status_code=410, detail="This link has already been used")
    try:
        exp = datetime.fromisoformat(doc["expires_at"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Malformed token") from exc
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This link has expired")
    email = doc["email"]
    # mask email → a***@example.com
    name, _, dom = email.partition("@")
    masked = f"{name[:1]}***@{dom}" if name and dom else email
    return {"ok": True, "email_masked": masked, "expires_at": doc["expires_at"]}


@router.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordIn):
    doc = await db.password_reset_tokens.find_one({"token": payload.token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    if doc.get("used_at"):
        raise HTTPException(status_code=410, detail="This link has already been used")
    try:
        exp = datetime.fromisoformat(doc["expires_at"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Malformed token") from exc
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This link has expired")

    user = await db.users.find_one({"id": doc["user_id"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )
    await db.password_reset_tokens.update_one(
        {"token": payload.token},
        {"$set": {"used_at": utcnow_iso()}},
    )
    await db.audit_log.insert_one({
        "id": new_id(),
        "actor_id": user["id"],
        "actor_email": user["email"],
        "action": "reset_password_self",
        "resource": "user",
        "resource_id": user["id"],
        "details": {"via": "email_link"},
        "created_at": utcnow_iso(),
    })
    return {"ok": True, "message": "Password updated. You can now sign in."}


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    payload: AdminResetPasswordIn,
    admin: dict = Depends(require_admin),
):
    """Admin-only manual password reset — bypasses the email flow.

    Useful when a user has lost email access. The admin can hand the new
    password to the user in person.
    """
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )
    # invalidate any outstanding self-service tokens for this user
    await db.password_reset_tokens.delete_many({"user_id": user_id, "used_at": None})
    await write_audit(admin, "admin_reset_password", "user", user_id, {"target_email": user["email"]})
    return {"ok": True, "message": "Password reset by admin."}
