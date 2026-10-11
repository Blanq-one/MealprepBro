"""Environment-only configuration (see .env.example)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

StructuredMode = Literal["strict", "best_effort"]


def sqlalchemy_url(url: str) -> str:
    """Hosted Postgres hands out libpq URLs (`postgres://`, `postgresql://`); SQLAlchemy needs the driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BACKEND_DIR.parent / ".env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://mealbro:mealbro@localhost:5432/mealbro"
    # Neon: DATABASE_URL is the pooled (-pooler, PgBouncer transaction mode) string the app uses; migrations
    # need a direct connection, DATABASE_URL_UNPOOLED (both are set by Neon's Vercel integration).
    database_url_unpooled: str | None = None
    test_database_url: str = "postgresql+psycopg://mealbro:mealbro@localhost:5433/mealbro_test"
    # Connection pool: "queue" keeps connections (a long-running server); "null" opens one per session and
    # closes it after (serverless, behind Neon's pooler). Unset = "null" on Vercel, else "queue".
    db_pool: Literal["queue", "null"] | None = None
    db_connect_timeout_seconds: int = Field(default=15, ge=1, le=120)  # Neon wakes from scale-to-zero
    db_connect_retries: int = Field(default=3, ge=0, le=10)
    vercel: str | None = None  # set to "1" by Vercel
    usda_raw_dir: Path = BACKEND_DIR.parent / "data" / "raw" / "usda"
    log_level: str = "INFO"

    # Auth (Phase 2): one password, checked against an scrypt hash (`python -m app.cli hash-password`), and an
    # HMAC-signed, HttpOnly session cookie.
    auth_password_hash: SecretStr | None = None
    session_secret: SecretStr | None = None
    session_cookie_secure: bool = True  # False only for plain-http testing on your home Wi-Fi
    session_max_age_days: int = Field(default=180, ge=1, le=400)
    allowed_origins: str = ""  # extra origins that may send changes (comma-separated); same-origin always may
    login_max_failures: int = Field(default=5, ge=1, le=100)  # per client within the window...
    login_max_failures_global: int = Field(default=20, ge=1, le=1000)  # ...and from everywhere together
    login_window_minutes: int = Field(default=15, ge=1, le=1440)

    # Planning runs inside one request (serverless: Vercel Hobby stops a function at 300 s). Every LLM call,
    # rate-limit wait and solve has to fit in this budget; validating and saving the plan come after it.
    plan_time_budget_seconds: int = Field(default=180, ge=30, le=270)
    plan_stale_after_seconds: int = Field(default=330, ge=60)  # older unfinished runs were cut off

    # LLM (Phase 1). Only app/llm/ reads these. The model name always comes from the environment.
    groq_api_key: SecretStr | None = None
    llm_provider: Literal["groq"] = "groq"
    llm_model: str | None = None
    llm_structured_mode: StructuredMode = "strict"  # anything else is a config error at startup
    llm_max_attempts: int = Field(default=3, ge=1, le=6)  # parse/validation attempts per call
    llm_max_transport_retries: int = Field(default=3, ge=0, le=6)  # 429 / timeouts, counted separately
    llm_timeout_seconds: float = Field(default=60, gt=0, le=600)
    # The lowest effort the configured model accepts ("low" for Groq's gpt-oss models); empty = the model has
    # no such setting. A value the provider rejects is a configuration error naming this variable (2b.3b).
    llm_reasoning_effort: str | None = "low"
    # a 2-recipe batch uses ~1,900 completion tokens including reasoning
    llm_max_completion_tokens: int = Field(default=3000, ge=256, le=32768)
    llm_daily_token_budget: int = Field(default=150_000, ge=0)  # rolling 24 h, below Groq's 200K/day
    llm_max_calls_per_run: int = Field(default=12, ge=1, le=100)
    llm_max_rate_wait_seconds: float = Field(default=60, ge=0)  # longest pause for a rate-limit reset
    # The per-minute token allowance assumed until the provider's x-ratelimit-limit-tokens header arrives
    llm_tokens_per_minute: int = Field(default=8000, ge=1000)
    # More ideas' background batch never leaves less than this much of the daily budget for calls you ask for
    llm_prefetch_daily_reserve: int = Field(default=30_000, ge=0)

    @field_validator("llm_reasoning_effort", mode="before")
    @classmethod
    def _blank_effort_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    # Solver (Phase 1)
    # The gaps usually stop the solver first (deterministic); a week that hits the limit returns its best plan
    # so far, marked "feasible" rather than "optimal". 30 s since Phase 2b (E7): the seed week needs about
    # 20-28 s to reach its gap (D43), and the 180 s plan budget cuts it further when time runs short.
    solver_time_limit_seconds: int = Field(default=30, ge=1, le=600)
    solver_gap_rel: float = Field(default=0.005, ge=0, le=0.2)
    solver_gap_abs: float = Field(default=1.0, ge=0, le=20)  # objective points (~$2 of groceries)

    @property
    def app_database_url(self) -> str:
        return sqlalchemy_url(self.database_url)

    @property
    def migration_database_url(self) -> str:
        return sqlalchemy_url(self.database_url_unpooled or self.database_url)

    @property
    def pool_mode(self) -> Literal["queue", "null"]:
        if self.db_pool is not None:
            return self.db_pool
        return "null" if self.vercel else "queue"


@lru_cache
def get_settings() -> Settings:
    return Settings()
