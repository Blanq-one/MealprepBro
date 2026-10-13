"""`.env.example` (step 2b.13, the 2b.6 approval item 12): every setting is listed, production's with a line
of its own, and only with placeholders: no key, password hash, session secret or cloud database password, so
the example can never pass the production safety checks (app/production.py)."""

import re

import pytest

from app.config import BACKEND_DIR, Settings
from app.production import production_problems

EXAMPLE = BACKEND_DIR.parent / ".env.example"
LINE = re.compile(r"^(#\s*)?([A-Z][A-Z0-9_]*)=(.*)$")
SET_BY_VERCEL = frozenset({"VERCEL", "VERCEL_ENV"})  # named in a comment, never given a value
PRODUCTION_NEEDS = frozenset(
    {
        "DATABASE_URL",
        "DATABASE_URL_UNPOOLED",
        "AUTH_PASSWORD_HASH",
        "SESSION_SECRET",
        "GROQ_API_KEY",
        "LLM_MODEL",
        "LLM_IDEAS_MODEL",
        "LLM_STRUCTURED_MODE",
        "RUN_MIGRATIONS_ON_DEPLOY",  # read by app/deploy.py, not a Settings field
    }
)
SECRETS = ("GROQ_API_KEY", "AUTH_PASSWORD_HASH", "SESSION_SECRET")
MODELS = ("LLM_MODEL", "LLM_IDEAS_MODEL")
DATABASE_URL = re.compile(r"postgres(?:ql)?(?:\+psycopg)?://[^\s)]+")

pytestmark = pytest.mark.skipif(
    not EXAMPLE.exists(), reason="no .env.example here (the fresh-clone image has backend/ only)"
)


def read_example() -> tuple[dict[str, str], set[str], str]:
    """The set lines (name -> value), the commented-out names, and the whole text."""
    text = EXAMPLE.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    commented: set[str] = set()
    for line in text.splitlines():
        if match := LINE.match(line.strip()):
            if match[1]:
                commented.add(match[2])
            else:
                values[match[2]] = match[3]
    return values, commented, text


def test_every_setting_is_listed() -> None:
    values, commented, text = read_example()
    names = {name.upper() for name in Settings.model_fields}
    assert sorted(names - SET_BY_VERCEL - values.keys() - commented) == []
    for name in SET_BY_VERCEL:
        assert name not in values
        assert re.search(rf"\b{name}\b", text), name


def test_every_production_setting_has_a_line_of_its_own() -> None:
    values, _, text = read_example()
    assert sorted(PRODUCTION_NEEDS - values.keys()) == []
    header = text.split("\n\n", 1)[0]  # the opening comment lists them for the Vercel step
    assert [name for name in sorted(PRODUCTION_NEEDS) if name not in header] == []


def test_secrets_and_models_are_placeholders() -> None:
    values, _, text = read_example()
    for name in SECRETS:
        assert values[name] == "" or values[name].startswith("your-"), name
    for name in MODELS:
        assert values[name].startswith("your-"), name
    assert not re.search(r"gsk_[A-Za-z0-9]{8,}", text)  # a Groq key
    assert "scrypt:" not in text  # a password hash
    for url in DATABASE_URL.findall(text):
        where = url.split("://", 1)[1].split("/", 1)[0]
        if "@" in where:
            credentials, host = where.rsplit("@", 1)
            # only docker compose's local databases (POSTGRES_PASSWORD=mealbro) or <user>:<password>
            assert host.startswith("localhost") or credentials == "<user>:<password>", url


def test_the_example_can_never_pass_as_production() -> None:
    values, _, _ = read_example()
    fields = {name.lower(): value for name, value in values.items() if name.lower() in Settings.model_fields}
    settings = Settings.model_validate({**fields, "vercel_env": "production"})  # these values only, no env
    problems = " | ".join(production_problems(settings))
    for says in (
        "SESSION_COOKIE_SECURE is false",
        "SESSION_SECRET is missing",
        "AUTH_PASSWORD_HASH is missing",
        "DATABASE_URL points at localhost",
    ):
        assert says in problems, problems
