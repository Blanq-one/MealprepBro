"""Shared LLM test helpers: settings for a given structured mode, and a fake clock for pacing."""

from dataclasses import dataclass, field
from typing import Any

from app.config import Settings


@dataclass
class FakeClock:
    now: float = 1000.0
    slept: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def make_settings(mode: str = "strict", **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "llm_structured_mode": mode,
        "llm_model": "fake-model",
        "llm_max_attempts": 3,
        "llm_max_transport_retries": 3,
        "llm_daily_token_budget": 150_000,
        "llm_max_calls_per_run": 12,
        **overrides,
    }
    return Settings(_env_file=None, **values)
