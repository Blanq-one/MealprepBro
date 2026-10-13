"""Production safety checks (step 2b.13, the 2b.6 approval item 11): the app refuses to start in production,
and the deploy refuses to build, on an insecure cookie, a missing or dev/example SESSION_SECRET or
AUTH_PASSWORD_HASH, or a database URL that points at localhost. Preview deployments and your PC aren't
checked."""

import secrets
from typing import Any

import pytest

from app import deploy
from app.auth.passwords import hash_password
from app.config import Settings
from app.production import UnsafeProductionError, check_production, production_problems

NEON = "postgresql://user:pass@ep-calm-dawn-123456-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
NEON_DIRECT = "postgresql://user:pass@ep-calm-dawn-123456.us-east-1.aws.neon.tech/neondb?sslmode=require"
STRONG_HASH = hash_password("a long production password")  # the real work factor
STRONG_SECRET = secrets.token_urlsafe(48)


def prod(**values: Any) -> Settings:
    base: dict[str, Any] = {
        "vercel": "1",
        "vercel_env": "production",
        "database_url": NEON,
        "database_url_unpooled": NEON_DIRECT,
        "auth_password_hash": STRONG_HASH,
        "session_secret": STRONG_SECRET,
        **values,
    }
    return Settings(_env_file=None, **base)


def test_a_safe_production_configuration_starts() -> None:
    assert production_problems(prod()) == []
    check_production(prod())
    assert production_problems(prod(vercel=None, vercel_env=None, app_env="production")) == []


@pytest.mark.parametrize(
    ("values", "says"),
    [
        ({"session_cookie_secure": False}, "SESSION_COOKIE_SECURE is false"),
        ({"session_secret": None}, "SESSION_SECRET is missing"),
        ({"session_secret": ""}, "SESSION_SECRET is missing"),
        ({"session_secret": "change-me"}, "SESSION_SECRET looks like a dev or example value"),
        ({"session_secret": "your-session-secret-goes-here-0123456789"}, "SESSION_SECRET looks like a dev"),
        ({"session_secret": "test-session-secret-0123456789abcdef"}, "SESSION_SECRET looks like a dev"),
        ({"session_secret": "a" * 64}, "SESSION_SECRET looks like a dev"),  # not random
        ({"auth_password_hash": None}, "AUTH_PASSWORD_HASH is missing"),
        ({"auth_password_hash": "your-password-hash"}, "AUTH_PASSWORD_HASH isn't a password hash"),
        ({"auth_password_hash": "scrypt:abc"}, "AUTH_PASSWORD_HASH isn't a password hash"),
        ({"auth_password_hash": hash_password("a long test password", n=2**10)}, "a test work factor"),
        (
            {"database_url": "postgresql+psycopg://mealbro:mealbro@localhost:5432/mealbro"},
            "points at localhost",
        ),
        ({"database_url": "postgresql://u:p@127.0.0.1/neondb"}, "points at 127.0.0.1"),
        (
            {"database_url_unpooled": "postgresql://mealbro:mealbro@db:5432/mealbro"},
            "DATABASE_URL_UNPOOLED points at db",
        ),
    ],
)
def test_each_unsafe_setting_refuses_to_start(values: dict[str, Any], says: str) -> None:
    settings = prod(**values)
    problems = production_problems(settings)
    assert any(says in p for p in problems), problems
    with pytest.raises(UnsafeProductionError, match="Refusing to start in production"):
        check_production(settings)


def test_empty_optional_values_count_as_unset() -> None:
    # .env.example's empty lines (DATABASE_URL_UNPOOLED=, APP_ENV=) mean "not set", never "a broken URL"
    assert production_problems(prod(database_url_unpooled="")) == []
    assert production_problems(prod(vercel_env="", app_env="", session_secret=None)) == []


def test_everything_wrong_at_once_is_listed_at_once() -> None:
    settings = prod(
        session_cookie_secure=False,
        session_secret=None,
        auth_password_hash=None,
        database_url_unpooled=None,
        database_url="postgresql+psycopg://mealbro:mealbro@localhost:5432/mealbro",
    )
    assert len(production_problems(settings)) == 4


def test_preview_deployments_and_your_pc_are_not_checked() -> None:
    local = Settings(_env_file=None, session_cookie_secure=False)  # the defaults: localhost, no secrets
    assert production_problems(local) == []
    assert (
        production_problems(
            prod(vercel_env="preview", session_secret=None, database_url="postgresql://u:p@localhost/x")
        )
        == []
    )


def test_the_deploy_build_stops_on_an_unsafe_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy, "get_settings", lambda: prod(session_secret="change-me"))
    assert deploy.main() == 1
    monkeypatch.setattr(deploy, "get_settings", prod)
    monkeypatch.setattr(deploy, "should_migrate", lambda env: (False, "skipping migrations"))
    assert deploy.main() == 0
