"""Login rate limiting, stored in the database (serverless instances share no memory).

At most LOGIN_MAX_FAILURES wrong passwords per client, and LOGIN_MAX_FAILURES_GLOBAL from everywhere
together, within LOGIN_WINDOW_MINUTES. A successful sign-in clears that client's count. The client is
recorded as an HMAC of its address, never the address."""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import LoginAttempt

KEEP_DAYS = 2  # attempts older than this are deleted as new ones arrive


@dataclass(frozen=True)
class Limits:
    per_client: int
    global_: int
    window: timedelta


class TooManyAttemptsError(Exception):
    def __init__(self, retry_after_s: int) -> None:
        super().__init__(f"too many wrong passwords; try again in {max(1, retry_after_s // 60)} min")
        self.retry_after_s = retry_after_s


def client_key(secret: str, address: str) -> str:
    return hmac.new(secret.encode(), address.encode(), hashlib.sha256).hexdigest()[:32]


def _failures_since(session: Session, since: datetime, key: str | None) -> tuple[int, datetime | None]:
    query = select(func.count(), func.min(LoginAttempt.occurred_at)).where(
        LoginAttempt.succeeded.is_(False), LoginAttempt.occurred_at >= since
    )
    if key is not None:
        last_ok = session.scalar(
            select(func.max(LoginAttempt.occurred_at)).where(
                LoginAttempt.client_key == key, LoginAttempt.succeeded.is_(True)
            )
        )
        query = query.where(LoginAttempt.client_key == key)
        if last_ok is not None and last_ok > since:
            query = query.where(LoginAttempt.occurred_at > last_ok)
    count, oldest = session.execute(query).one()
    return int(count), oldest


def check(session: Session, key: str, limits: Limits, now: datetime) -> None:
    """Raises TooManyAttemptsError (with how long to wait) when this client or everyone together is over."""
    since = now - limits.window
    for scope, cap in ((key, limits.per_client), (None, limits.global_)):
        count, oldest = _failures_since(session, since, scope)
        if count >= cap:
            wait = (oldest + limits.window - now) if oldest is not None else limits.window
            raise TooManyAttemptsError(int(wait.total_seconds()) + 1)


def record(session: Session, key: str, succeeded: bool, now: datetime) -> None:
    session.add(LoginAttempt(client_key=key, succeeded=succeeded, occurred_at=now))
    session.execute(delete(LoginAttempt).where(LoginAttempt.occurred_at < now - timedelta(days=KEEP_DAYS)))
    session.flush()
