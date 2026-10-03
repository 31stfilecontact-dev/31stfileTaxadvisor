"""Clerk session verification and firm membership checks."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
import os
import re
import threading
import time
from urllib.parse import urlsplit

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import HTTPException, Request, status

from backend.config import settings

logger = logging.getLogger("tax_advisor.auth")

_EMAIL_CACHE_TTL_SECONDS = 120
_email_cache: dict[str, tuple[float, str | None]] = {}
_email_cache_lock = threading.Lock()


@dataclass(frozen=True)
class TeamMember:
    user_id: str
    email: str


def parse_team_email_allowlist(value: str | None) -> tuple[set[str], set[str]]:
    """Return exact email addresses and exact-or-subdomain email domains."""
    emails: set[str] = set()
    domains: set[str] = set()
    for raw_item in re.split(r"[\s,;]+", value or ""):
        item = raw_item.strip().lower()
        if not item:
            continue
        if "@" in item and not item.startswith("@"):
            if re.fullmatch(r"[^@\s]+@[^@\s]+", item):
                emails.add(item)
            continue
        domain = item.lstrip("@").rstrip(".")
        if domain and not any(char in domain for char in "*/"):
            domains.add(domain)
    return emails, domains


def is_team_email_allowed(email: str, allowlist: str | None) -> bool:
    exact_emails, domains = parse_team_email_allowlist(allowlist)
    normalized = email.strip().lower()
    if normalized in exact_emails:
        return True
    _, separator, email_domain = normalized.rpartition("@")
    if not separator:
        return False
    return any(
        email_domain == domain or email_domain.endswith(f".{domain}")
        for domain in domains
    )


def _authorized_parties() -> list[str]:
    """Build Clerk's azp allowlist from the app's Replit-managed hostnames."""
    origins: list[str] = []
    for key in ("REPLIT_DOMAINS", "REPLIT_DEV_DOMAIN"):
        for candidate in os.getenv(key, "").split(","):
            candidate = candidate.strip()
            if not candidate:
                continue
            parsed = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
            if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
                continue
            origin = f"https://{parsed.netloc}"
            if origin not in origins:
                origins.append(origin)
    return origins


@lru_cache(maxsize=1)
def _clerk_client(secret_key: str) -> Clerk:
    return Clerk(bearer_auth=secret_key)


def _primary_verified_email(user_id: str, clerk: Clerk) -> str | None:
    now = time.monotonic()
    with _email_cache_lock:
        cached = _email_cache.get(user_id)
        if cached and cached[0] > now:
            return cached[1]

    try:
        user = clerk.users.get(user_id=user_id)
    except Exception as exc:
        logger.warning(
            "Clerk user lookup failed",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Team access could not be verified. Please retry shortly.",
        ) from exc

    primary_id = getattr(user, "primary_email_address_id", None)
    primary_email = None
    for address in getattr(user, "email_addresses", []) or []:
        if getattr(address, "id", None) != primary_id:
            continue
        verification = getattr(address, "verification", None)
        verification_status = getattr(verification, "status", None)
        verification_status = getattr(verification_status, "value", verification_status)
        value = getattr(address, "email_address", None)
        if value and str(verification_status).lower() == "verified":
            primary_email = str(value).strip().lower()
        break

    with _email_cache_lock:
        if len(_email_cache) > 2048:
            expired = [key for key, (expires, _) in _email_cache.items() if expires <= now]
            for key in expired:
                _email_cache.pop(key, None)
        _email_cache[user_id] = (now + _EMAIL_CACHE_TTL_SECONDS, primary_email)
    return primary_email


def get_current_member(request: Request) -> TeamMember:
    """Require a verified Clerk session belonging to the configured firm team."""
    secret_key = settings.clerk_secret_key
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Team sign-in is not configured.",
        )
    allowed_emails, allowed_domains = parse_team_email_allowlist(
        settings.team_email_allowlist
    )
    if not allowed_emails and not allowed_domains:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Team access is not configured.",
        )

    authorized_parties = _authorized_parties()
    if not authorized_parties:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application sign-in origins are not configured.",
        )

    clerk = _clerk_client(secret_key)
    clerk_request = httpx.Request(
        method=request.method,
        url=str(request.url),
        headers=dict(request.headers.items()),
    )
    try:
        auth_state = clerk.authenticate_request(
            clerk_request,
            AuthenticateRequestOptions(authorized_parties=authorized_parties),
        )
    except Exception as exc:
        logger.warning(
            "Clerk session verification failed",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity verification is temporarily unavailable.",
        ) from exc

    if not getattr(auth_state, "is_signed_in", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid team sign-in is required.",
        )

    payload = getattr(auth_state, "payload", None)
    user_id = payload.get("sub") if isinstance(payload, dict) else None
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The team sign-in could not be identified.",
        )

    email = _primary_verified_email(user_id, clerk)
    if not email or not is_team_email_allowed(email, settings.team_email_allowlist):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized for the firm workspace.",
        )
    return TeamMember(user_id=user_id, email=email)