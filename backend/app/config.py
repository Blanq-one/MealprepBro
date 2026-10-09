"""Environment-only configuration (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BACKEND_DIR.parent / ".env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://mealbro:mealbro@localhost:5432/mealbro"
    test_database_url: str = "postgresql+psycopg://mealbro:mealbro@localhost:5433/mealbro_test"
    usda_raw_dir: Path = BACKEND_DIR.parent / "data" / "raw" / "usda"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
