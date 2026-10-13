from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import DbSession
from app.auth import rate_limit, sessions
from app.auth.client_address import client_address
from app.auth.dependencies import (
    AppSettings,
    AuthError,
    check_origin,
    clear_session_cookie,
    now_s,
    require_session,
    session_secret,
    set_session_cookie,
)
from app.auth.passwords import verify_password
from app.config import Settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"], dependencies=[Depends(check_origin)])
SignedIn = Annotated[sessions.Session, Depends(require_session)]


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=200)


class SessionOut(BaseModel):
    signed_in: bool
    expires_at: datetime


def request_address(request: Request, settings: Settings) -> str:
    """The real client address (PD1): Vercel's own header on Vercel, a trusted proxy's X-Forwarded-For behind
    TRUSTED_PROXIES, else the socket's peer (auth/client_address.py)."""
    return client_address(
        request.headers,
        request.client.host if request.client else None,
        on_vercel=bool(settings.vercel),
        trusted=settings.trusted_proxy_set,
    )


@router.post("/login", status_code=204, response_class=Response)
def login(body: LoginIn, request: Request, session: DbSession, settings: AppSettings) -> Response:
    """Sign in with the app password. Sets a long-lived HttpOnly session cookie; wrong passwords are rate
    limited (429 with Retry-After)."""
    secret = session_secret(settings)
    if settings.auth_password_hash is None or not settings.auth_password_hash.get_secret_value():
        raise AuthError(503, "Sign-in isn't set up", "Set AUTH_PASSWORD_HASH (see docs/deploy.md).")
    key = rate_limit.client_key(secret, request_address(request, settings))
    limits = rate_limit.Limits(
        settings.login_max_failures,
        settings.login_max_failures_global,
        timedelta(minutes=settings.login_window_minutes),
    )
    now = datetime.now(UTC)
    try:
        rate_limit.check(session, key, limits, now)
    except rate_limit.TooManyAttemptsError as exc:
        raise AuthError(
            429, "Too many tries", str(exc), headers={"Retry-After": str(exc.retry_after_s)}
        ) from exc
    ok = verify_password(body.password, settings.auth_password_hash.get_secret_value())
    rate_limit.record(session, key, ok, now)
    session.commit()
    if not ok:
        raise AuthError(401, "Wrong password", "That password isn't right.")
    response = Response(status_code=204)
    set_session_cookie(response, sessions.issue(secret, now_s()), settings)
    return response


@router.post("/logout", status_code=204, response_class=Response)
def logout(settings: AppSettings) -> Response:
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response


@router.get("/session", response_model=SessionOut)
def current_session(settings: AppSettings, signed_in: SignedIn) -> SessionOut:
    """200 when the cookie is valid (and renewed if it's over a day old), else 401."""
    expires = signed_in.issued_at + settings.session_max_age_days * 86400
    return SessionOut(signed_in=True, expires_at=datetime.fromtimestamp(expires, UTC))
