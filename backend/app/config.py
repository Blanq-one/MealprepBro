"""Environment-only configuration (see .env.example)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

StructuredMode = Literal["strict", "best_effort"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BACKEND_DIR.parent / ".env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://mealbro:mealbro@localhost:5432/mealbro"
    test_database_url: str = "postgresql+psycopg://mealbro:mealbro@localhost:5433/mealbro_test"
    usda_raw_dir: Path = BACKEND_DIR.parent / "data" / "raw" / "usda"
    log_level: str = "INFO"

    # LLM (Phase 1). Only app/llm/ reads these. The model name always comes from the environment.
    groq_api_key: SecretStr | None = None
    llm_provider: Literal["groq"] = "groq"
    llm_model: str | None = None
    llm_structured_mode: StructuredMode = "strict"  # anything else is a config error at startup
    llm_max_attempts: int = Field(default=3, ge=1, le=6)  # parse/validation attempts per call
    llm_max_transport_retries: int = Field(default=3, ge=0, le=6)  # 429 / timeouts, counted separately
    llm_timeout_seconds: float = Field(default=60, gt=0, le=600)
    llm_reasoning_effort: str | None = "low"
    # a 2-recipe batch uses ~1,900 completion tokens including reasoning
    llm_max_completion_tokens: int = Field(default=3000, ge=256, le=32768)
    llm_daily_token_budget: int = Field(default=150_000, ge=0)  # rolling 24 h, below Groq's 200K/day
    llm_max_calls_per_run: int = Field(default=12, ge=1, le=100)
    llm_max_rate_wait_seconds: float = Field(default=60, ge=0)  # longest pause for a rate-limit reset

    # Solver (Phase 1)
    # The gaps usually stop the solver first (deterministic); a week that hits the limit returns its best plan
    # so far, marked "feasible" rather than "optimal" (BUILD_PLAN AC 1.12: < 15 s).
    solver_time_limit_seconds: int = Field(default=12, ge=1, le=600)
    solver_gap_rel: float = Field(default=0.005, ge=0, le=0.2)
    solver_gap_abs: float = Field(default=1.0, ge=0, le=20)  # objective points (~$2 of groceries)


@lru_cache
def get_settings() -> Settings:
    return Settings()
