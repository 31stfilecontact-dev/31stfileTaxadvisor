"""Password verification and short-lived, server-signed admin sessions."""

import hashlib
import hmac
import os
import secrets
import time

from fastapi import Cookie, HTTPException, Request, Response

from backend.config import settings

ADMIN_COOKIE_NAME = "tax_admin_session"
ADMIN_SESSION_TTL_SECONDS = 8 * 60 * 60


def _signature(payload: str) -> str:
    secret = settings.session_secret
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Admin sessions are not configured. Set SESSION_SECRET on the server.",
        )
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _valid_session(cookie_value: str | None) -> bool:
    if not cookie_value:
        return False
    parts = cookie_value.split(".")
    if len(parts) != 3:
        return False
    timestamp_text, nonce, supplied_signature = parts
    if not timestamp_text.isdigit() or not nonce:
        return False
    issued_at = int(timestamp_text)
    now = int(time.time())
    if issued_at > now + 60 or now - issued_at > ADMIN_SESSION_TTL_SECONDS:
        return False
    payload = f"{timestamp_text}.{nonce}"
    expected_signature = _signature(payload)
    return hmac.compare_digest(supplied_signature, expected_signature)


def create_admin_session(password: str, request: Request, response: Response) -> None:
    configured_password = settings.admin_password
    if not configured_password:
        raise HTTPException(
            status_code=503,
            detail="Admin access is not configured. Set ADMIN_PASSWORD on the server.",
        )
    if not settings.session_secret:
        raise HTTPException(
            status_code=503,
            detail="Admin sessions are not configured. Set SESSION_SECRET on the server.",
        )
    if not hmac.compare_digest(password, configured_password):
        raise HTTPException(status_code=401, detail="Admin password is incorrect.")

    timestamp = str(int(time.time()))
    payload = f"{timestamp}.{secrets.token_urlsafe(18)}"
    token = f"{payload}.{_signature(payload)}"
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    secure = bool(os.getenv("REPL_ID")) or request.url.scheme == "https" or forwarded_proto == "https"
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        max_age=ADMIN_SESSION_TTL_SECONDS,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/api/admin",
    )


def clear_admin_session(request: Request, response: Response) -> None:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    secure = (
        bool(os.getenv("REPL_ID"))
        or request.url.scheme == "https"
        or forwarded_proto == "https"
    )
    response.delete_cookie(
        key=ADMIN_COOKIE_NAME,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/api/admin",
    )


def require_admin(
    cookie_value: str | None = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
) -> None:
    if not settings.admin_password:
        raise HTTPException(
            status_code=503,
            detail="Admin access is not configured. Set ADMIN_PASSWORD on the server.",
        )
    if not settings.session_secret:
        raise HTTPException(
            status_code=503,
            detail="Admin sessions are not configured. Set SESSION_SECRET on the server.",
        )
    if not _valid_session(cookie_value):
        raise HTTPException(status_code=401, detail="Admin session is missing or expired.")