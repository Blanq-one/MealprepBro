"""Engine and session factory.

Serverless-safe (Phase 2): on Vercel every session gets its own connection (NullPool) to Neon's pooled
endpoint, which runs PgBouncer in transaction mode, so nothing assumes a long-lived connection. Psycopg's
automatic server-side prepared statements are off, and connecting retries a few times with back-off, since
a Neon compute waking from scale-to-zero can refuse or drop the first attempt.
"""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
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
# what a request says when the database didn't answer even after the retries (AC5): a 503 to try again
DATABASE_SLOW_TITLE = "Taking longer than usual"
DATABASE_SLOW_DETAIL = "The database didn't answer in time; try again in a moment."
DATABASE_RETRY_AFTER_S = 5
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


@dataclass
class ConnectLog:
    """The database connections opened while it is active, for a run record (the tier cards', AC5): a Neon
    compute waking from scale-to-zero shows as a slow connect or a retried one."""

    connects: int = 0  # connections opened
    attempts: int = 0  # tries, failed ones included
    seconds: float = 0.0  # spent connecting, back-off included
    failed: int = 0  # connections that failed after every retry

    @property
    def retries(self) -> int:
        return self.attempts - self.connects - self.failed

    def record(self, attempts: int, seconds: float, *, ok: bool = True) -> None:
        self.connects += ok
        self.failed += not ok
        self.attempts += attempts
        self.seconds += seconds


_connect_log: ContextVar[ConnectLog | None] = ContextVar("connect_log", default=None)


@contextmanager
def logging_connects() -> Iterator[ConnectLog]:
    """Every connection this thread opens inside the block is counted in the log it yields."""
    record = ConnectLog()
    token = _connect_log.set(record)
    try:
        yield record
    finally:
        _connect_log.reset(token)


def active_connect_log() -> ConnectLog | None:
    return _connect_log.get()


def count_connects_into(record: ConnectLog) -> None:
    """From now on, this thread's connections count in `record`: for a worker thread of its own (a stream's),
    which ends with its work, so nothing has to reset it."""
    _connect_log.set(record)


def connect_with_retry[T](
    connect: Callable[[], T],
    retries: int,
    *,
    base_delay_s: float = RETRY_BASE_DELAY_S,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `connect`, retrying transient OperationalErrors with exponential back-off (0.5 s, 1 s, 2 s...)."""
    started = time.monotonic()
    record = _connect_log.get()
    for attempt in range(retries + 1):
        try:
            connection = connect()
        except psycopg.OperationalError as exc:
            if attempt >= retries or not is_transient(exc):
                if record is not None:
                    record.record(attempt + 1, time.monotonic() - started, ok=False)
                raise
            delay = base_delay_s * 2**attempt
            log.warning("database connection failed (%s); retrying in %.1f s", exc, delay)
            sleep(delay)
            continue
        if record is not None:
            record.record(attempt + 1, time.monotonic() - started)
        return connection
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
