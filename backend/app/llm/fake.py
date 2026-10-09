"""FakeLLMClient: scripted responses for tests and offline runs. Never touches the network."""

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.llm.client import LLMRequest, LLMResponse, RateLimitInfo

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "testing" / "fixtures" / "llm_responses"

Scripted = LLMResponse | Exception | Callable[[LLMRequest], LLMResponse]


def response(
    text: str | dict[str, Any],
    *,
    finish_reason: str = "stop",
    prompt_tokens: int = 900,
    completion_tokens: int = 600,
    rate_limit: RateLimitInfo | None = None,
) -> LLMResponse:
    body = text if isinstance(text, str) else json.dumps(text)
    return LLMResponse(
        text=body,
        finish_reason=finish_reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=5,
        rate_limit=rate_limit or RateLimitInfo(),
    )


def fixture_text(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def fixture_response(name: str, **kwargs: Any) -> LLMResponse:
    return response(fixture_text(name), **kwargs)


class UnexpectedLLMCallError(AssertionError):
    """Raised by FakeLLMClient(fail_if_called=True): the code path was supposed to need zero calls."""


@dataclass
class FakeLLMClient:
    """Returns scripted items in order (a response, an exception to raise, or a callable). When the script
    runs out, `default` (if given) answers every further call."""

    script: list[Scripted] = field(default_factory=list)
    default: Scripted | None = None
    fail_if_called: bool = False
    provider: str = "fake"
    model: str = "fake-model"
    requests: list[LLMRequest] = field(default_factory=list)

    @classmethod
    def failing(cls) -> "FakeLLMClient":
        return cls(fail_if_called=True)

    def extend(self, items: Iterable[Scripted]) -> None:
        self.script.extend(items)

    def complete(self, request: LLMRequest) -> LLMResponse:
        if self.fail_if_called:
            raise UnexpectedLLMCallError("the LLM was called, but this path must make zero LLM calls")
        self.requests.append(request)
        item = self.script.pop(0) if self.script else self.default
        if item is None:
            raise AssertionError("FakeLLMClient: no scripted response left")
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(request)
        return item

    @property
    def calls(self) -> int:
        return len(self.requests)
