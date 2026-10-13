"""Serverless-safe database connections (Phase 2 pre-work: Vercel functions + Neon's pooled endpoint)."""

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool, QueuePool

from app.config import Settings, sqlalchemy_url
from app.db.session import (
    active_connect_log,
    connect_with_retry,
    engine_options,
    logging_connects,
    make_engine,
)

NEON = "postgresql://me:pw@ep-cool-name-123456-pooler.us-east-1.aws.neon.tech/mealbro?sslmode=require"
NEON_DIRECT = "postgres://me:pw@ep-cool-name-123456.us-east-1.aws.neon.tech/mealbro?sslmode=require"


def settings(**values) -> Settings:
    return Settings(_env_file=None, **values)


def test_hosted_libpq_urls_get_the_psycopg_driver():
    assert sqlalchemy_url(NEON).startswith("postgresql+psycopg://me:pw@ep-cool-name-123456-pooler.")
    assert sqlalchemy_url(NEON_DIRECT).startswith("postgresql+psycopg://me:pw@ep-cool-name-123456.us")
    assert sqlalchemy_url("postgresql+psycopg://x@h/db") == "postgresql+psycopg://x@h/db"


def test_migrations_use_the_direct_connection_and_the_app_the_pooled_one():
    s = settings(database_url=NEON, database_url_unpooled=NEON_DIRECT)
    assert "-pooler" in s.app_database_url and "-pooler" not in s.migration_database_url
    assert settings(database_url=NEON).migration_database_url == s.app_database_url  # locally: one URL


def test_on_vercel_every_session_opens_its_own_short_lived_connection(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("DB_POOL", raising=False)
    assert settings().pool_mode == "queue"
    monkeypatch.setenv("VERCEL", "1")
    on_vercel = settings()
    assert on_vercel.pool_mode == "null"
    options = engine_options(on_vercel)
    assert options["poolclass"] is NullPool and options["pool_pre_ping"]
    # PgBouncer in transaction mode: no automatic server-side prepared statements; wait for a waking compute
    assert options["connect_args"] == {"connect_timeout": 15, "prepare_threshold": None}
    assert settings(db_pool="queue").pool_mode == "queue"  # an explicit setting wins


def test_a_long_running_server_recycles_connections_before_neon_scales_to_zero():
    options = engine_options(settings(db_pool="queue"))
    assert "poolclass" not in options and options["pool_recycle"] < 300


def test_connecting_retries_transient_failures_with_back_off():
    calls: list[int] = []
    slept: list[float] = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise psycopg.OperationalError("connection to server failed: Connection refused")
        return "connected"

    assert connect_with_retry(flaky, 3, sleep=slept.append) == "connected"
    assert len(calls) == 3 and slept == [0.5, 1.0]


def test_connecting_gives_up_after_the_retries_and_at_once_on_a_wrong_password():
    slept: list[float] = []

    def down() -> None:
        raise psycopg.OperationalError("timeout expired")

    with pytest.raises(psycopg.OperationalError, match="timeout expired"):
        connect_with_retry(down, 2, sleep=slept.append)
    assert slept == [0.5, 1.0]
    slept.clear()

    def refused() -> None:
        raise psycopg.OperationalError('password authentication failed for user "me"')

    with pytest.raises(psycopg.OperationalError, match="password authentication"):
        connect_with_retry(refused, 3, sleep=slept.append)
    assert slept == []


def test_a_run_record_can_count_the_connections_and_their_retries():
    """AC5: inside logging_connects, every connection (and every retry, and a failure) is counted, so a run
    record can say a Neon compute was waking up; outside it nothing is kept."""
    calls: list[int] = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise psycopg.OperationalError("connection to server failed: Connection refused")
        return "connected"

    def down() -> None:
        raise psycopg.OperationalError("timeout expired")

    assert active_connect_log() is None
    with logging_connects() as record:
        assert connect_with_retry(flaky, 3, sleep=lambda _s: None) == "connected"
        with pytest.raises(psycopg.OperationalError):
            connect_with_retry(down, 1, sleep=lambda _s: None)
    assert (record.connects, record.attempts, record.failed, record.retries) == (1, 4, 1, 2)
    assert record.seconds >= 0 and active_connect_log() is None
    connect_with_retry(flaky, 3, sleep=lambda _s: None)  # nothing active: nothing counted
    assert record.connects == 1


def test_the_engine_connects_through_the_retrying_hook(test_db_url):
    engine = make_engine(test_db_url, settings(db_pool="null"))
    try:
        assert isinstance(engine.pool, NullPool)
        with logging_connects() as record, engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
        assert record.connects == 1 and record.retries == 0
    finally:
        engine.dispose()
    pooled = make_engine(test_db_url, settings(db_pool="queue"))
    try:
        assert isinstance(pooled.pool, QueuePool)
    finally:
        pooled.dispose()
