"""Stateless session tokens: `v1.<issued unix seconds>.<nonce>.<signature>`, signed with HMAC-SHA256 over
everything before the signature. A token is valid until it is older than SESSION_MAX_AGE_DAYS; the app
renews the cookie as you use it, so the installed PWA stays signed in. Rotating SESSION_SECRET signs every
device out."""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

VERSION = "v1"
COOKIE_NAME = "mealbro_session"
RENEW_AFTER_SECONDS = 24 * 3600  # re-issue the cookie at most once a day


@dataclass(frozen=True)
class Session:
    issued_at: int

    def age(self, now: int) -> int:
        return now - self.issued_at


def _sign(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def issue(secret: str, now: int) -> str:
    payload = f"{VERSION}.{now}.{secrets.token_urlsafe(12)}"
    return f"{payload}.{_sign(secret, payload)}"


def read(token: str | None, secret: str, now: int, max_age_s: int) -> Session | None:
    """The session, or None when the token is missing, tampered with, from the future or expired."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != VERSION:
        return None
    payload, signature = ".".join(parts[:3]), parts[3]
    if not hmac.compare_digest(_sign(secret, payload), signature):
        return None
    try:
        issued = int(parts[1])
    except ValueError:
        return None
    if issued > now + 60 or now - issued > max_age_s:
        return None
    return Session(issued)
