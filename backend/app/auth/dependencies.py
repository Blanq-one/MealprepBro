"""FastAPI dependencies: `check_origin` on every API route that changes something, `require_session` on
every API route except sign-in and /health."""

import time
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request, Response

from app.api.problems import ProblemError
from app.auth import sessions
from app.config import Settings, get_settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class AuthError(ProblemError):
    """Not signed in, sign-in not set up, a cross-site change, or too many tries."""


AppSettings = Annotated[Settings, Depends(get_settings)]


def now_s() -> int:
    return int(time.time())


def session_secret(settings: Settings) -> str:
    if settings.session_secret is None or not settings.session_secret.get_secret_value():
        raise AuthError(
            503,
            "Sign-in isn't set up",
            "Set AUTH_PASSWORD_HASH and SESSION_SECRET (see docs/deploy.md).",
        )
    return settings.session_secret.get_secret_value()


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        sessions.COOKIE_NAME,
        token,
        max_age=settings.session_max_age_days * 86400,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        sessions.COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )


def _host_of(origin: str) -> str | None:
    parts = urlsplit(origin)
    return parts.netloc.lower() if parts.scheme in ("http", "https") and parts.netloc else None


def check_origin(request: Request, settings: AppSettings) -> None:
    """Changes must come from this app's own pages: the Origin (or Referer) host must be the host the request
    was sent to (behind a proxy, the forwarded host) or one of ALLOWED_ORIGINS."""
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    host = _host_of(origin)
    if host is None:
        raise AuthError(403, "Cross-site request refused", "This request didn't say which site sent it.")
    allowed = {
        h.lower()
        for h in (request.headers.get("host"), request.headers.get("x-forwarded-host"))
        if h is not None
    }
    allowed |= {h for o in settings.allowed_origins.split(",") if (h := _host_of(o.strip())) is not None}
    if host not in allowed:
        raise AuthError(403, "Cross-site request refused", f"Requests from {host} aren't accepted.")


def require_session(request: Request, response: Response, settings: AppSettings) -> sessions.Session:
    secret = session_secret(settings)
    now = now_s()
    session = sessions.read(
        request.cookies.get(sessions.COOKIE_NAME), secret, now, settings.session_max_age_days * 86400
    )
    if session is None:
        raise AuthError(401, "Not signed in", "Sign in to continue.")
    if session.age(now) > sessions.RENEW_AFTER_SECONDS:  # sliding: in regular use it never expires
        set_session_cookie(response, sessions.issue(secret, now), settings)
    return session
