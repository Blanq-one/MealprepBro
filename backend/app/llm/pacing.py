"""Rate-limit pacing from the provider's own headers (never hardcoded limits), and the run / day budgets."""

import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import LlmCall
from app.llm.client import RateLimitInfo
from app.llm.errors import LLMBudgetExceededError, LLMCallCapError


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class Pacer:
    """Waits before a call when the last response said the minute's tokens or requests are used up, and
    computes back-off waits for 429s (retry-after first) and timeouts."""

    clock: Clock
    max_wait_s: float
    last: RateLimitInfo | None = None
    last_at: float | None = None
    waited_s: list[float] = field(default_factory=list)

    def observe(self, info: RateLimitInfo) -> None:
        self.last, self.last_at = info, self.clock.monotonic()

    def before_call(self, estimated_tokens: int) -> None:
        if self.last is None or self.last_at is None:
            return
        elapsed = self.clock.monotonic() - self.last_at
        waits = []
        if self.last.remaining_tokens is not None and self.last.remaining_tokens < estimated_tokens:
            waits.append((self.last.reset_tokens_s or 0) - elapsed)
        if self.last.remaining_requests is not None and self.last.remaining_requests <= 0:
            waits.append((self.last.reset_requests_s or 0) - elapsed)
        wait = min(max(waits, default=0), self.max_wait_s)
        if wait > 0:
            self._sleep(wait)

    def backoff(self, retry: int, retry_after_s: float | None) -> None:
        wait = retry_after_s if retry_after_s is not None else float(2**retry)
        self._sleep(min(max(wait, 0), self.max_wait_s))

    def _sleep(self, seconds: float) -> None:
        self.waited_s.append(seconds)
        self.clock.sleep(seconds)


@dataclass
class CallBudget:
    """LLM_MAX_CALLS_PER_RUN: every attempt that reaches the provider counts."""

    max_calls: int
    used: int = 0

    def take(self) -> None:
        if self.used >= self.max_calls:
            raise LLMCallCapError(
                f"this run reached the limit of {self.max_calls} LLM calls (LLM_MAX_CALLS_PER_RUN)",
                detail={"max_calls": self.max_calls},
            )
        self.used += 1


@dataclass
class TokenGuard:
    """LLM_DAILY_TOKEN_BUDGET over a rolling 24 hours, summed from the llm_call log."""

    session: Session
    daily_budget: int

    def used_last_24h(self) -> int:
        since = func.now() - timedelta(hours=24)
        total = self.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        func.coalesce(LlmCall.prompt_tokens, 0) + func.coalesce(LlmCall.completion_tokens, 0)
                    ),
                    0,
                )
            ).where(LlmCall.created_at >= since)
        )
        return int(total or 0)

    def check(self, estimated_tokens: int) -> None:
        used = self.used_last_24h()
        if used + estimated_tokens > self.daily_budget:
            raise LLMBudgetExceededError(
                f"the daily LLM token budget would be exceeded ({used:,} used in the last 24 hours, about "
                f"{estimated_tokens:,} more needed, budget {self.daily_budget:,}; LLM_DAILY_TOKEN_BUDGET)",
                detail={"used": used, "estimated": estimated_tokens, "budget": self.daily_budget},
            )
