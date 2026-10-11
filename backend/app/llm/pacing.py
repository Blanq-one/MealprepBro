"""Rate-limit pacing from the provider's own headers (never hardcoded limits), and the run / day budgets.

Step 2b.3b (FLOW_SPEC §13.2, §15.1):
  * before each call the pacer compares the call's estimated tokens (prompt + its maximum completion) with
    the per-minute allowance left, read from the x-ratelimit-* headers and refilled at limit / 60 a second;
  * prompts are estimated from their characters (CHARS_PER_TOKEN = 4) and calibrated per purpose: the median
    ratio of real to estimated prompt tokens over the last 20 logged calls of that purpose (2.5 until five are
    logged; 1.2 before that, from the 2b.3b live test), so predicted waits match the provider's;
  * a wait longer than LLM_MAX_RATE_WAIT_SECONDS, or than what is left of the request's time budget, raises
    LLMWaitTooLongError with `retry_after_s`: the request ends gracefully, never with a problem error.
The last headers are shared by every run in this process (one rate state per provider and model), so a second
request inside the same minute knows what the first one used.
"""

import json
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import LlmCall
from app.llm.client import Message, RateLimitInfo
from app.llm.errors import LLMBudgetExceededError, LLMCallCapError, LLMDeadlineError, LLMWaitTooLongError

# An LLM call is started only with at least this much of the request's time budget left, and a rate-limit
# wait never eats into it (a 2-recipe batch takes about 10-20 s).
MIN_CALL_SECONDS = 25.0
CALL_TIMEOUT_MARGIN_S = 5.0
CHARS_PER_TOKEN = 4  # the raw estimate, calibrated per purpose below
# Real ÷ estimated prompt tokens until five calls of a purpose are logged. The 2b.3b live test measured
# 1.03-1.11 (the planned 2.5 assumed a fixed 3.5K overhead that doesn't exist); 1.2 keeps a margin (§15.1).
DEFAULT_PROMPT_RATIO = 1.2
CALIBRATION_WINDOW = 20
CALIBRATION_MIN_CALLS = 5
MINUTE_SHARE = 0.95  # each call's prompt estimate + maximum completion stays within 95% of the minute's limit


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass(frozen=True)
class Deadline:
    """The end of one request's time budget, on a monotonic clock. A serverless function is stopped at a hard
    limit (Vercel Hobby: 300 s), so planning finishes inside its request and checks this before every LLM
    call, rate-limit wait and solve."""

    clock: Clock
    at: float

    @classmethod
    def after(cls, clock: Clock, seconds: float) -> "Deadline":
        return cls(clock, clock.monotonic() + seconds)

    def remaining(self) -> float:
        return max(self.at - self.clock.monotonic(), 0.0)

    def call_timeout(self, configured_s: float) -> float:
        """The timeout for the next LLM call. Raises LLMDeadlineError when too little time is left."""
        left = self.remaining()
        if left < MIN_CALL_SECONDS:
            raise LLMDeadlineError(
                f"only {left:.0f} s of this request's time budget is left, too little for another recipe "
                "generation call",
                detail={"remaining_s": round(left, 1)},
            )
        return min(configured_s, left - CALL_TIMEOUT_MARGIN_S)

    def check_wait(self, wait_s: float) -> None:
        """A rate-limit wait is allowed only when a call still fits after it."""
        left = self.remaining()
        if wait_s > left - MIN_CALL_SECONDS:
            raise LLMWaitTooLongError(
                f"the recipe service asks to wait {wait_s:.0f} s, but this request has {left:.0f} s left",
                retry_after_s=wait_s,
                detail={"wait_s": round(wait_s, 1), "remaining_s": round(left, 1)},
            )


@dataclass
class RateState:
    """The provider's last word on the per-minute allowance (its headers and when they arrived)."""

    info: RateLimitInfo | None = None
    at: float | None = None  # monotonic time of the response that carried them


_STATES: dict[tuple[str, str], RateState] = {}


def rate_state(provider: str, model: str) -> RateState:
    """The rate state every run of this process shares for one provider and model."""
    return _STATES.setdefault((provider, model), RateState())


def reset_rate_states() -> None:
    """Forget every provider's headers (tests)."""
    _STATES.clear()


@dataclass
class Pacer:
    """Waits before a call when the minute's allowance can't cover it yet, and computes back-off waits for
    429s (retry-after first) and timeouts. A wait over `max_wait_s`, or one that would leave no time for the
    call under the deadline, raises LLMWaitTooLongError instead of sleeping."""

    clock: Clock
    max_wait_s: float
    state: RateState = field(default_factory=RateState)
    fallback_limit: int = 8000  # LLM_TOKENS_PER_MINUTE, until a header says otherwise
    waited_s: list[float] = field(default_factory=list)
    deadline: Deadline | None = None
    on_wait: Callable[[float], None] | None = None  # progress hook ("waiting N s for the rate limit")

    def observe(self, info: RateLimitInfo) -> None:
        if info == RateLimitInfo():  # no headers at all: keep what we knew
            return
        self.state.info, self.state.at = info, self.clock.monotonic()

    def minute_limit(self) -> int:
        info = self.state.info
        return info.limit_tokens if info is not None and info.limit_tokens else self.fallback_limit

    def call_budget(self) -> int:
        """The most one call may ask for: prompt estimate + maximum completion (95% of the minute)."""
        return int(self.minute_limit() * MINUTE_SHARE)

    def wait_for(self, needed: int) -> float:
        """Seconds until the minute's allowance covers `needed` tokens (0 when it already does)."""
        info, at = self.state.info, self.state.at
        if info is None or at is None:
            return 0.0
        elapsed = self.clock.monotonic() - at
        needed = min(needed, self.call_budget())
        waits = []
        if info.remaining_tokens is not None:
            if info.limit_tokens:
                rate = info.limit_tokens / 60.0
                available = min(float(info.limit_tokens), info.remaining_tokens + elapsed * rate)
                if available < needed:
                    waits.append((needed - available) / rate)
            elif info.remaining_tokens < needed:
                waits.append((info.reset_tokens_s or 0) - elapsed)
        if info.remaining_requests is not None and info.remaining_requests <= 0:
            waits.append((info.reset_requests_s or 0) - elapsed)
        return max(max(waits, default=0.0), 0.0)

    def before_call(self, needed: int) -> None:
        wait = self.wait_for(needed)
        if wait > 0:
            self._sleep(wait)

    def backoff(self, retry: int, retry_after_s: float | None) -> None:
        wait = retry_after_s if retry_after_s is not None else float(2**retry)
        self._sleep(max(wait, 0))

    def _sleep(self, seconds: float) -> None:
        if self.deadline is not None:
            self.deadline.check_wait(seconds)
        if seconds > self.max_wait_s:
            raise LLMWaitTooLongError(
                f"the recipe service needs a {seconds:.0f} s pause, longer than the "
                f"{self.max_wait_s:.0f} s this request waits (LLM_MAX_RATE_WAIT_SECONDS)",
                retry_after_s=seconds,
                detail={"wait_s": round(seconds, 1)},
            )
        if self.on_wait is not None:
            self.on_wait(seconds)
        self.waited_s.append(seconds)
        self.clock.sleep(seconds)


def raw_estimate(messages: Sequence[Message], schema: dict[str, Any] | None) -> float:
    """Prompt tokens from characters: the messages plus the transport schema (sent with every call)."""
    chars = sum(len(m["content"]) for m in messages)
    if schema is not None:
        chars += len(json.dumps(schema, separators=(",", ":")))
    return chars / CHARS_PER_TOKEN


def prompt_ratio(session: Session, purpose: str, schema: dict[str, Any] | None) -> float:
    """The median real ÷ estimated prompt tokens over the last 20 logged calls of this purpose (1.2 until
    five are logged)."""
    rows = session.execute(
        select(LlmCall.request_messages, LlmCall.prompt_tokens)
        .where(LlmCall.purpose == purpose, LlmCall.prompt_tokens.is_not(None))
        .order_by(LlmCall.created_at.desc(), LlmCall.id.desc())
        .limit(CALIBRATION_WINDOW)
    ).all()
    ratios = []
    for messages, tokens in rows:
        estimate = raw_estimate(messages or [], schema)
        if estimate > 0 and tokens:
            ratios.append(tokens / estimate)
    if len(ratios) < CALIBRATION_MIN_CALLS:
        return DEFAULT_PROMPT_RATIO
    return float(statistics.median(ratios))


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

    def check(self, estimated_tokens: int, reserve: int = 0) -> None:
        """`reserve`: tokens that must stay unspent after this call (the background batch keeps 30K for
        calls you ask for)."""
        used = self.used_last_24h()
        if used + estimated_tokens > self.daily_budget - reserve:
            raise LLMBudgetExceededError(
                f"the daily LLM token budget would be exceeded ({used:,} used in the last 24 hours, about "
                f"{estimated_tokens:,} more needed, budget {self.daily_budget:,}"
                + (f" with {reserve:,} kept in reserve" if reserve else "")
                + "; LLM_DAILY_TOKEN_BUDGET)",
                detail={"used": used, "estimated": estimated_tokens, "budget": self.daily_budget},
            )
