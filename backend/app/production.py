"""Production safety checks (step 2b.13, the 2b.6 approval item 11): the app refuses to start in production,
and the deploy's build step refuses to go on, when a setting would make the live app unsafe:

  - SESSION_COOKIE_SECURE is false (the sign-in cookie would also travel over plain http);
  - SESSION_SECRET is missing, short, or a dev or example value (anyone could sign session cookies);
  - AUTH_PASSWORD_HASH is missing, isn't a hash `python -m app.cli hash-password` makes, or was made with a
    test work factor (cheap to guess);
  - DATABASE_URL (or DATABASE_URL_UNPOOLED) points at this machine or at docker compose's local databases.

Production is Vercel's production environment (VERCEL_ENV=production) or APP_ENV=production on another host;
preview deployments and your PC are never checked.
"""

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.auth.passwords import N
from app.config import Settings

MIN_SECRET_CHARS = 32  # `hash-password` makes 64
MIN_SECRET_DISTINCT = 12  # a real random secret uses many different characters
MAKE_ONE = "make a new one with `python -m app.cli hash-password`"
DEV_SECRETS = frozenset(
    {
        "change-me",
        "changeme",
        "dev",
        "dev-secret",
        "secret",
        "example",
        "mealbro",
        "test-session-secret-0123456789abcdef",  # the test suite's
    }
)
PLACEHOLDER_PREFIXES = ("your-", "your_", "<", "replace", "example", "changeme", "change-me")
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "db", "db-test", "host.docker.internal"})


class UnsafeProductionError(RuntimeError):
    """The production settings aren't safe to run with; the message lists every problem."""


def is_production(settings: Settings) -> bool:
    return settings.vercel_env == "production" or settings.app_env == "production"


def _placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered in DEV_SECRETS or lowered.startswith(PLACEHOLDER_PREFIXES)


def _secret_problem(settings: Settings) -> str | None:
    secret = settings.session_secret.get_secret_value() if settings.session_secret else ""
    if not secret.strip():
        return "SESSION_SECRET is missing"
    if _placeholder(secret) or len(secret) < MIN_SECRET_CHARS or len(set(secret)) < MIN_SECRET_DISTINCT:
        return f"SESSION_SECRET looks like a dev or example value: {MAKE_ONE}"
    return None


def _hash_problem(settings: Settings) -> str | None:
    encoded = settings.auth_password_hash.get_secret_value() if settings.auth_password_hash else ""
    if not encoded.strip():
        return "AUTH_PASSWORD_HASH is missing"
    parts = encoded.split(":")
    if _placeholder(encoded) or len(parts) != 6 or parts[0] != "scrypt" or not all(p.strip() for p in parts):
        return f"AUTH_PASSWORD_HASH isn't a password hash: {MAKE_ONE}"
    try:
        n = int(parts[1])
    except ValueError:
        return f"AUTH_PASSWORD_HASH isn't a password hash: {MAKE_ONE}"
    if n < N:
        return f"AUTH_PASSWORD_HASH was made with a test work factor: {MAKE_ONE}"
    return None


def _database_problems(settings: Settings) -> list[str]:
    out = []
    for name, url in (
        ("DATABASE_URL", settings.database_url),
        ("DATABASE_URL_UNPOOLED", settings.database_url_unpooled),
    ):
        if not url:
            continue
        try:
            host = (make_url(url).host or "localhost").lower()
        except ArgumentError:
            out.append(f"{name} isn't a database URL")
            continue
        if host in LOCAL_HOSTS or host.startswith("127."):
            out.append(f"{name} points at {host}, a local database, not your Neon one")
    return out


def production_problems(settings: Settings) -> list[str]:
    """Every reason the production settings are unsafe (empty: fine, or not production)."""
    if not is_production(settings):
        return []
    problems = []
    if not settings.session_cookie_secure:
        problems.append(
            "SESSION_COOKIE_SECURE is false: leave it unset in production (the cookie must be Secure)"
        )
    for check in (_secret_problem, _hash_problem):
        if (problem := check(settings)) is not None:
            problems.append(problem)
    problems += _database_problems(settings)
    return problems


def check_production(settings: Settings) -> None:
    """Raises UnsafeProductionError listing every problem, in production."""
    if problems := production_problems(settings):
        raise UnsafeProductionError(
            "Refusing to start in production: " + "; ".join(problems) + " (see docs/deploy.md)."
        )
