"""Engine and session factory.

Serverless-safe (Phase 2): on Vercel every session gets its own connection (NullPool) to Neon's pooled
endpoint, which runs PgBouncer in transaction mode, so nothing assumes a long-lived connection. Psycopg's
automatic server-side prepared statements are off, and connecting retries a few times with back-off, since
a Neon compute waking from scale-to-zero can refuse or drop the first attempt.
"""

import logging
import time
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Any

import psycopg
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

POOL_RECYCLE_SECONDS = 240  # under Neon's 5-minute scale-to-zero: never reuse a connection it may have closed
RETRY_BASE_DELAY_S = 0.5
# Errors that retrying can't fix (wrong password, missing database): fail at once.
PERMANENT_CONNECT_ERRORS = ("password authentication failed", "does not exist", "no pg_hba.conf entry")


def engine_options(settings: Settings) -> dict[str, Any]:
    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": settings.db_connect_timeout_seconds, "prepare_threshold": None},
    }
    if settings.pool_mode == "null":
        options["poolclass"] = NullPool
    else:
        options["pool_recycle"] = POOL_RECYCLE_SECONDS
    return options


def is_transient(exc: Exception) -> bool:
    message = str(exc).lower()
    return not any(text in message for text in PERMANENT_CONNECT_ERRORS)


def connect_with_retry[T](
    connect: Callable[[], T],
    retries: int,
    *,
    base_delay_s: float = RETRY_BASE_DELAY_S,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `connect`, retrying transient OperationalErrors with exponential back-off (0.5 s, 1 s, 2 s...)."""
    for attempt in range(retries + 1):
        try:
            return connect()
        except psycopg.OperationalError as exc:
            if attempt >= retries or not is_transient(exc):
                raise
            delay = base_delay_s * 2**attempt
            log.warning("database connection failed (%s); retrying in %.1f s", exc, delay)
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def make_engine(url: str, settings: Settings) -> Engine:
    engine = create_engine(url, **engine_options(settings))

    @event.listens_for(engine, "do_connect")
    def _connect(dialect: Any, _record: Any, cargs: Any, cparams: Any) -> Any:
        return connect_with_retry(lambda: dialect.connect(*cargs, **cparams), settings.db_connect_retries)

    return engine


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return make_engine(settings.app_database_url, settings)


def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
