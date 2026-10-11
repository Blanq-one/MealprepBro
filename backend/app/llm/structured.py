"""One path for structured LLM output in both modes (§6.3):

    request (strict: true | false) → parse JSON → Pydantic → domain hook → retry with concise errors
    → LLMOutputError after LLM_MAX_ATTEMPTS

Transport failures (429, timeouts) are retried separately (≤ LLM_MAX_TRANSPORT_RETRIES, honoring
retry-after) and are not validation attempts. Every attempt that reaches the provider is logged to
`llm_call` with its mode and outcome; attempts after the first chain to the previous one.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import GenerationRun, LlmCall
from app.llm.client import LLMClient, LLMRequest, LLMResponse, Message
from app.llm.errors import (
    LLMConfigError,
    LLMOutputError,
    LLMProviderOutputError,
    LLMRateLimitedError,
    LLMReasoningEffortError,
    LLMStrictUnsupportedError,
    LLMTimeoutError,
    LLMTransportError,
    LLMTruncatedError,
)
from app.llm.pacing import (
    CallBudget,
    Clock,
    Deadline,
    Pacer,
    RateState,
    SystemClock,
    TokenGuard,
    prompt_ratio,
    rate_state,
    raw_estimate,
)
from app.llm.schema import schema_summary, transport_schema

MAX_FEEDBACK_ERRORS = 12
# A failed reply is sent back with the retry only when it is short: re-sending a long one makes every attempt
# bigger, and Groq's free tier rejects a request over 8K tokens per minute outright (HTTP 413).
MAX_ECHO_CHARS = 2000


@dataclass(frozen=True)
class StructuredSpec[T: BaseModel]:
    purpose: str  # candidate_generation | recipe_revision | ...
    prompt_version: str
    messages: tuple[Message, ...]
    response_model: type[T]
    # Whole-response domain check: a non-empty list of errors triggers a retry with those errors.
    domain_check: Callable[[T], list[str]] | None = None
    raise_on_truncation: bool = False  # batch callers halve the batch instead of retrying
    max_completion_tokens: int | None = None  # per purpose (2b.3b); None = LLM_MAX_COMPLETION_TOKENS
    daily_reserve: int = 0  # tokens of the daily budget this call must leave unspent (the background batch)
    # A batch whose reply fails as a whole (the provider rejected it, or one item broke the model) keeps the
    # items that validate on their own; None = the whole reply must validate (2b.3b, ideas only)
    salvage: Callable[[Any], T | None] | None = None


@dataclass(frozen=True)
class CallEstimate:
    """What one call is expected to cost: its calibrated prompt, and with its maximum completion."""

    prompt_tokens: int
    max_completion_tokens: int

    @property
    def minute_tokens(self) -> int:
        """Checked against the minute's allowance: the provider seems to count the maximum completion."""
        return self.prompt_tokens + self.max_completion_tokens

    @property
    def daily_tokens(self) -> int:
        """Checked against the daily guard: about half the maximum completion is usually used."""
        return self.prompt_tokens + self.max_completion_tokens // 2


@dataclass
class StructuredResult[T: BaseModel]:
    value: T
    call_ids: list[int]
    final_call_id: int
    attempts: int


@dataclass
class LLMRunContext:
    """Everything one run needs to talk to the LLM: client, logging session, caps and pacing."""

    client: LLMClient
    session: Session
    settings: Settings
    run_id: int | None = None
    clock: Clock = field(default_factory=SystemClock)
    deadline: Deadline | None = None  # the request's time budget: planning runs inside one request
    on_wait: Callable[[float], None] | None = None
    rate: RateState | None = None  # None = the process-wide state for this client's provider and model
    calls: CallBudget = field(init=False)
    tokens: TokenGuard = field(init=False)
    pacer: Pacer = field(init=False)

    def __post_init__(self) -> None:
        self.calls = CallBudget(self.settings.llm_max_calls_per_run)
        self.tokens = TokenGuard(self.session, self.settings.llm_daily_token_budget)
        self.pacer = Pacer(
            self.clock,
            self.settings.llm_max_rate_wait_seconds,
            state=self.rate or rate_state(self.client.provider, self.client.model),
            fallback_limit=self.settings.llm_tokens_per_minute,
            deadline=self.deadline,
            on_wait=self.on_wait,
        )

    @property
    def strict(self) -> bool:
        return self.settings.llm_structured_mode == "strict"

    def generate[T: BaseModel](self, spec: StructuredSpec[T]) -> StructuredResult[T]:
        return _generate(self, spec)

    def prompt_estimate(
        self, purpose: str, messages: Sequence[Message], response_model: type[BaseModel]
    ) -> int:
        """The calibrated prompt tokens of a call (messages and transport schema), as sent in this mode."""
        schema = transport_schema(response_model)
        sent = tuple(messages) if self.strict else _system_with_summary(tuple(messages), schema)
        return _calibrated(self, purpose, sent, schema)

    def estimate(self, spec: StructuredSpec[Any]) -> CallEstimate:
        prompt = self.prompt_estimate(spec.purpose, spec.messages, spec.response_model)
        return CallEstimate(prompt, _max_completion(self, spec))


def _schema_name(model: type[BaseModel]) -> str:
    return model.__name__


def _max_completion(ctx: LLMRunContext, spec: StructuredSpec[Any]) -> int:
    return spec.max_completion_tokens or ctx.settings.llm_max_completion_tokens


def _calibrated(
    ctx: LLMRunContext, purpose: str, messages: Sequence[Message], schema: dict[str, Any] | None
) -> int:
    return int(raw_estimate(messages, schema) * prompt_ratio(ctx.session, purpose, schema)) + 1


def _system_with_summary(messages: tuple[Message, ...], schema: dict[str, Any]) -> tuple[Message, ...]:
    """best_effort: the schema is also summarized in the system prompt."""
    summary = "Reply with one JSON object with exactly these fields:\n" + schema_summary(schema)
    if messages and messages[0]["role"] == "system":
        first = {"role": "system", "content": messages[0]["content"] + "\n\n" + summary}
        return (first, *messages[1:])
    return ({"role": "system", "content": summary}, *messages)


def _validation_feedback(exc: ValidationError) -> list[str]:
    errors = []
    for e in exc.errors()[:MAX_FEEDBACK_ERRORS]:
        loc = ".".join(str(part) for part in e["loc"]) or "(top level)"
        errors.append(f"{loc}: {e['msg']}")
    return errors


def _record(
    ctx: LLMRunContext,
    spec: StructuredSpec[Any],
    *,
    attempt: int,
    parent_id: int | None,
    messages: Sequence[Message],
    response: LLMResponse | None,
    outcome: str,
    error_detail: dict[str, Any] | None = None,
) -> LlmCall:
    row = LlmCall(
        generation_run_id=ctx.run_id,
        parent_call_id=parent_id,
        purpose=spec.purpose,
        provider=ctx.client.provider,
        model=ctx.client.model,
        structured_mode=ctx.settings.llm_structured_mode,
        prompt_version=spec.prompt_version,
        attempt=attempt,
        request_messages=list(messages),
        response_schema=_schema_name(spec.response_model),
        response_text=response.text if response else None,
        finish_reason=response.finish_reason if response else None,
        outcome=outcome,
        error_detail=error_detail,
        prompt_tokens=response.prompt_tokens if response else None,
        completion_tokens=response.completion_tokens if response else None,
        latency_ms=response.latency_ms if response else None,
    )
    ctx.session.add(row)
    if ctx.run_id is not None:
        run = ctx.session.get(GenerationRun, ctx.run_id)
        if run is not None:
            run.llm_call_count += 1
            run.total_tokens += response.total_tokens if response else 0
    ctx.session.flush()
    return row


def _call_with_transport_retries(
    ctx: LLMRunContext,
    spec: StructuredSpec[Any],
    request: LLMRequest,
    *,
    attempt: int,
    parent_id: int | None,
    call_ids: list[int],
) -> tuple[LLMResponse | None, LLMProviderOutputError | None, int | None]:
    """Returns (response, provider output error, last logged call id). Raises after the transport retries."""
    retries = 0
    schema = dict(request.json_schema) if request.json_schema is not None else None
    estimate = CallEstimate(
        _calibrated(ctx, spec.purpose, request.messages, schema), request.max_completion_tokens
    )
    while True:
        ctx.calls.take()
        ctx.tokens.check(estimate.daily_tokens, reserve=spec.daily_reserve)
        ctx.pacer.before_call(estimate.minute_tokens)
        if ctx.deadline is not None:
            request = replace(request, timeout_s=ctx.deadline.call_timeout(ctx.settings.llm_timeout_seconds))
        try:
            response = ctx.client.complete(request)
        except LLMRateLimitedError as exc:
            row = _record(
                ctx,
                spec,
                attempt=attempt,
                parent_id=parent_id,
                messages=request.messages,
                response=None,
                outcome="rate_limited",
                error_detail={"retry_after_s": exc.retry_after_s},
            )
            call_ids.append(row.id)
            parent_id = row.id
            if retries >= ctx.settings.llm_max_transport_retries:
                raise LLMRateLimitedError(
                    f"still rate limited after {retries + 1} tries; try again in a minute",
                    retry_after_s=exc.retry_after_s,
                    detail={"call_ids": list(call_ids)},
                ) from exc
            ctx.pacer.backoff(retries, exc.retry_after_s)
            retries += 1
            continue
        except (LLMTimeoutError, LLMTransportError) as exc:
            outcome = "transport_error"
            row = _record(
                ctx,
                spec,
                attempt=attempt,
                parent_id=parent_id,
                messages=request.messages,
                response=None,
                outcome=outcome,
                error_detail={"error": str(exc), "kind": exc.code},
            )
            call_ids.append(row.id)
            parent_id = row.id
            if retries >= ctx.settings.llm_max_transport_retries:
                raise type(exc)(
                    f"{exc} (after {retries + 1} tries)", detail={"call_ids": list(call_ids)}
                ) from exc
            ctx.pacer.backoff(retries, None)
            retries += 1
            continue
        except LLMStrictUnsupportedError as exc:
            row = _record(
                ctx,
                spec,
                attempt=attempt,
                parent_id=parent_id,
                messages=request.messages,
                response=None,
                outcome="transport_error",
                error_detail={"error": str(exc)},
            )
            call_ids.append(row.id)
            raise LLMConfigError(
                f"the model '{ctx.client.model}' does not support strict structured outputs; "
                "set LLM_STRUCTURED_MODE=best_effort (or choose a model that supports strict mode)",
                detail={"provider_message": str(exc)},
            ) from exc
        except LLMReasoningEffortError as exc:
            row = _record(
                ctx,
                spec,
                attempt=attempt,
                parent_id=parent_id,
                messages=request.messages,
                response=None,
                outcome="transport_error",
                error_detail={"error": str(exc)},
            )
            call_ids.append(row.id)
            raise LLMConfigError(
                f"the model '{ctx.client.model}' doesn't accept LLM_REASONING_EFFORT="
                f"'{request.reasoning_effort}'; set it to the lowest value the model's Groq docs list, or "
                "leave it empty for a model without that setting",
                detail={"provider_message": str(exc)},
            ) from exc
        except LLMProviderOutputError as exc:
            return None, exc, parent_id
        ctx.pacer.observe(response.rate_limit)
        return response, None, parent_id


def _generate[T: BaseModel](ctx: LLMRunContext, spec: StructuredSpec[T]) -> StructuredResult[T]:
    schema = transport_schema(spec.response_model)
    base = spec.messages if ctx.strict else _system_with_summary(spec.messages, schema)
    messages: list[Message] = list(base)
    call_ids: list[int] = []
    parent_id: int | None = None
    last_errors: list[str] = []
    for attempt in range(1, ctx.settings.llm_max_attempts + 1):
        request = LLMRequest(
            messages=tuple(messages),
            schema_name=_schema_name(spec.response_model),
            json_schema=schema,
            strict=ctx.strict,
            max_completion_tokens=_max_completion(ctx, spec),
            reasoning_effort=ctx.settings.llm_reasoning_effort,
        )
        response, provider_error, parent_id = _call_with_transport_retries(
            ctx, spec, request, attempt=attempt, parent_id=parent_id, call_ids=call_ids
        )
        text = response.text if response else (provider_error.failed_output if provider_error else None)
        if provider_error is not None:
            last_errors = [
                f"the provider rejected the output as invalid JSON for the schema: {provider_error}"
            ]
            kept = _salvaged(spec, text)
            if kept is not None:
                return _kept(
                    ctx,
                    spec,
                    kept,
                    attempt=attempt,
                    parent_id=parent_id,
                    messages=messages,
                    response=None,
                    errors=last_errors,
                    call_ids=call_ids,
                )
            row = _record(
                ctx,
                spec,
                attempt=attempt,
                parent_id=parent_id,
                messages=messages,
                response=None,
                outcome="parse_error",
                error_detail={"errors": last_errors},
            )
        elif response is not None and response.finish_reason == "length":
            last_errors = ["the reply was cut off at the token limit; it must be shorter"]
            row = _record(
                ctx,
                spec,
                attempt=attempt,
                parent_id=parent_id,
                messages=messages,
                response=response,
                outcome="parse_error",
                error_detail={"errors": last_errors, "truncated": True},
            )
            if spec.raise_on_truncation:
                call_ids.append(row.id)
                raise LLMTruncatedError(
                    "the LLM reply was cut off at the token limit", detail={"call_ids": call_ids}
                )
        else:
            assert response is not None
            try:
                payload = json.loads(response.text or "")
            except json.JSONDecodeError as exc:
                last_errors = [
                    f"the reply was not valid JSON ({exc.msg} at position {exc.pos}); reply with only "
                    "the JSON object, no prose or code fences"
                ]
                row = _record(
                    ctx,
                    spec,
                    attempt=attempt,
                    parent_id=parent_id,
                    messages=messages,
                    response=response,
                    outcome="parse_error",
                    error_detail={"errors": last_errors},
                )
            else:
                try:
                    value = spec.response_model.model_validate(payload)
                except ValidationError as exc:
                    last_errors = _validation_feedback(exc)
                    kept = _salvaged(spec, response.text)
                    if kept is not None:
                        return _kept(
                            ctx,
                            spec,
                            kept,
                            attempt=attempt,
                            parent_id=parent_id,
                            messages=messages,
                            response=response,
                            errors=last_errors,
                            call_ids=call_ids,
                        )
                    row = _record(
                        ctx,
                        spec,
                        attempt=attempt,
                        parent_id=parent_id,
                        messages=messages,
                        response=response,
                        outcome="validation_error",
                        error_detail={"errors": last_errors},
                    )
                else:
                    domain_errors = spec.domain_check(value) if spec.domain_check else []
                    if not domain_errors:
                        row = _record(
                            ctx,
                            spec,
                            attempt=attempt,
                            parent_id=parent_id,
                            messages=messages,
                            response=response,
                            outcome="ok",
                        )
                        call_ids.append(row.id)
                        return StructuredResult(value, call_ids, row.id, attempt)
                    last_errors = domain_errors[:MAX_FEEDBACK_ERRORS]
                    row = _record(
                        ctx,
                        spec,
                        attempt=attempt,
                        parent_id=parent_id,
                        messages=messages,
                        response=response,
                        outcome="domain_error",
                        error_detail={"errors": last_errors},
                    )
        call_ids.append(row.id)
        parent_id = row.id
        echo = bool(text) and len(text or "") <= MAX_ECHO_CHARS
        if echo:
            messages.append({"role": "assistant", "content": text or ""})
        messages.append({"role": "user", "content": _retry_message(last_errors, echoed=echo)})
    raise LLMOutputError(
        f"the LLM output was still invalid after {ctx.settings.llm_max_attempts} attempts: "
        + "; ".join(last_errors),
        detail={"call_ids": call_ids, "errors": last_errors},
    )


def _salvaged[T: BaseModel](spec: StructuredSpec[T], text: str | None) -> T | None:
    """The items of a failed batch that validate on their own (spec.salvage), or None."""
    if spec.salvage is None or not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    kept = spec.salvage(payload)
    if kept is None or (spec.domain_check is not None and spec.domain_check(kept)):
        return None
    return kept


def _kept[T: BaseModel](
    ctx: LLMRunContext,
    spec: StructuredSpec[T],
    value: T,
    *,
    attempt: int,
    parent_id: int | None,
    messages: Sequence[Message],
    response: LLMResponse | None,
    errors: list[str],
    call_ids: list[int],
) -> StructuredResult[T]:
    """A salvaged batch: logged as ok, with the errors of the items it dropped."""
    row = _record(
        ctx,
        spec,
        attempt=attempt,
        parent_id=parent_id,
        messages=messages,
        response=response,
        outcome="ok",
        error_detail={"salvaged": True, "errors": errors},
    )
    call_ids.append(row.id)
    return StructuredResult(value, call_ids, row.id, attempt)


def _retry_message(errors: Sequence[str], echoed: bool = True) -> str:
    bullets = "\n".join(f"- {e}" for e in errors)
    note = "" if echoed else " (it isn't repeated here, to stay within the token limit)"
    return (
        f"Your previous reply{note} had these problems:\n"
        f"{bullets}\n"
        "Fix every one of them and reply again with the complete JSON object only."
    )
