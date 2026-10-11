"""Real Groq calls through the full validation path, opt-in only, so normal runs never spend rate limits:

RUN_LIVE_LLM_TESTS=1 uv run pytest -m live_llm -s

Step 2b.3b (AC 7) measures two-stage generation in one run of about 4 calls (~25K tokens), all with the
configured reasoning effort, waiting on the real per-minute limit between them:
  1. the Phase 1 batch (full GeneratedRecipeBatch schema);
  2. one ideas call (RecipeIdeaBatch schema);
  3. the same ideas messages in plain JSON mode with no schema: the difference in Groq's prompt tokens is what
     the schema costs;
  4. one steps call (RecipeSteps, the smallest schema);
  then a tiny probe (about 100 tokens): a request whose prompt + maximum completion is just over the minute's
  limit, to see whether Groq counts the maximum completion in its per-minute check.
It prints each call's real prompt and completion tokens, the effort used and what the text explains, and the
findings go in FLOW_SPEC §15.1.
"""

import json
import os
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.cook import answers as answers_mod
from app.cook.ideas import meal_now_request
from app.cook.pool import load_pool
from app.cook.search import rank_pool
from app.db.models import GenerationRun, Ingredient, LlmCall
from app.domain.enums import MealSlot, StorageLocation
from app.llm.client import LLMRequest, LLMResponse, make_client
from app.llm.errors import LLMError
from app.llm.pacing import Deadline, SystemClock, raw_estimate
from app.llm.prompts import recipe_ideas
from app.llm.schema import transport_schema
from app.llm.structured import LLMRunContext
from app.planning.candidates import CandidateGenerator, gap_analysis
from app.planning.ideas import IdeaGenerator
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.planning.resolver import IngredientResolver
from app.planning.steps import StepsWriter
from app.schemas.cook import CookAnswers
from app.schemas.llm_recipe import GeneratedRecipeBatch, RecipeIdeaBatch, RecipeSteps
from app.schemas.plans import PlanRequest
from app.services.inventory import LotInput, add_lot
from app.services.settings import current_user, load_settings

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_LLM_TESTS") != "1", reason="set RUN_LIVE_LLM_TESTS=1 to call Groq"
    ),
]


def schema_chars(model: Any) -> int:
    return len(json.dumps(transport_schema(model), separators=(",", ":")))


def report(label: str, rows: list[LlmCall], schema: int, extra: str = "") -> dict[str, Any]:
    """Every attempt's tokens; the analysis uses the first attempt Groq counted (its messages are the prompt
    as built, before any retry message)."""
    attempts = [
        {
            "attempt": r.attempt,
            "outcome": r.outcome,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "salvaged": bool((r.error_detail or {}).get("salvaged")),
        }
        for r in rows
    ]
    counted = next((r for r in rows if r.prompt_tokens), None)
    out: dict[str, Any] = {"call": label, "attempts": attempts, "schema_chars": schema}
    if counted is not None:
        text_tokens = round(raw_estimate(counted.request_messages, None))
        out.update(
            prompt_tokens=counted.prompt_tokens,
            completion_tokens=counted.completion_tokens,
            text_tokens_chars_over_4=text_tokens,
            unexplained=(counted.prompt_tokens or 0) - text_tokens - schema // 4,
            ratio_to_raw_estimate=round((counted.prompt_tokens or 0) / max(1, text_tokens + schema // 4), 2),
        )
    print(f"\n[{label}] {json.dumps(out)} {extra}")
    return out


def calls(session: Any, purpose: str) -> list[LlmCall]:
    return list(session.scalars(select(LlmCall).where(LlmCall.purpose == purpose).order_by(LlmCall.id)))


def test_two_stage_generation_token_report(seeded_db):
    settings = get_settings()
    user = current_user(seeded_db)
    client = make_client(settings)
    clock = SystemClock()
    effort = settings.llm_reasoning_effort
    print(f"\nmodel={settings.llm_model} mode={settings.llm_structured_mode} reasoning_effort={effort}")
    findings: dict[str, Any] = {"model": settings.llm_model, "effort": effort}

    def context(purpose: str) -> LLMRunContext:
        run = GenerationRun(user_id=user.id, purpose=purpose, status="running")
        seeded_db.add(run)
        seeded_db.flush()
        return LLMRunContext(client, seeded_db, settings, run.id, clock, deadline=Deadline.after(clock, 240))

    # 1. the Phase 1 batch (full schema), as in Phase 1's live run
    c = constraints_for(
        seeded_db,
        user.id,
        PlanRequest(week_start=date(2026, 10, 12), slot_kcal={MealSlot.DINNER: 550, MealSlot.DRINK: 100}),
    )
    problem = build_problem(seeded_db, user.id, c)
    gaps = gap_analysis(problem)
    assert [g.slot for g in gaps] == [MealSlot.DRINK]
    generator = CandidateGenerator(seeded_db, user.id, context("weekly_plan"))
    created = generator.generate(problem, gaps)
    findings["phase1"] = report(
        "phase1 batch", calls(seeded_db, "candidate_generation"), schema_chars(GeneratedRecipeBatch)
    )
    assert created, generator.dropped

    # 2. one ideas call for a meal-now search with a thin pantry
    thighs = seeded_db.scalars(
        select(Ingredient.id).where(Ingredient.slug == "chicken-thigh-boneless-skinless")
    )
    add_lot(seeded_db, user.id, LotInput(thighs.one(), Decimal(700), "g", StorageLocation.FRIDGE))
    answers = CookAnswers(mode="now", slot=MealSlot.DINNER, goals=["high_protein"])
    user_settings = load_settings(seeded_db, user.id)
    query = answers_mod.resolve(answers, user_settings, datetime.now(ZoneInfo(user.timezone)))
    pool = load_pool(seeded_db, user.id, user_settings, query)
    resolver = IngredientResolver(seeded_db, user.id)
    req = meal_now_request(
        seeded_db,
        user.id,
        user_settings,
        query,
        pool,
        resolver=resolver,
        on_screen=[card["title"] for card in rank_pool(seeded_db, pool, query).cards],
    )
    ideas_ctx = context("meal_now")
    ideas = IdeaGenerator(seeded_db, user.id, ideas_ctx, resolver)
    size = ideas.size(req)
    outcome = ideas.generate(req, revise=False)
    idea_rows = calls(seeded_db, "recipe_ideas")
    findings["ideas"] = report(
        "ideas",
        idea_rows,
        schema_chars(RecipeIdeaBatch),
        f"asked={size.count} max_completion={size.max_completion_tokens} passed={len(outcome.passed)} "
        f"dropped={json.dumps(outcome.dropped)[:600]}",
    )
    findings["ideas"]["asked"] = size.count
    findings["ideas"]["passed"] = len(outcome.passed)

    # 3. the same ideas messages in plain JSON mode (no schema): what the schema costs
    messages = recipe_ideas.build_messages(req.context(size.count))
    ideas_ctx.pacer.before_call(size.prompt_tokens + size.max_completion_tokens)
    plain: LLMResponse = client.complete(
        LLMRequest(
            messages=messages,
            schema_name="RecipeIdeaBatch",
            json_schema=None,
            strict=False,
            max_completion_tokens=size.max_completion_tokens,
            reasoning_effort=effort,
        )
    )
    ideas_ctx.pacer.observe(plain.rate_limit)
    first = next((r for r in idea_rows if r.attempt == 1 and r.prompt_tokens), None)  # the same messages
    schema_cost = (first.prompt_tokens or 0) - (plain.prompt_tokens or 0) if first is not None else None
    findings["plain_json"] = {
        "prompt_tokens": plain.prompt_tokens,
        "completion_tokens": plain.completion_tokens,
        "schema_cost_tokens": schema_cost,
    }
    print(
        f"\n[plain json] {json.dumps(findings['plain_json'])} remaining={plain.rate_limit.remaining_tokens}"
    )

    # 4. one steps call (smallest schema) for the first passing idea
    assert outcome.passed, outcome.dropped
    writer = StepsWriter(
        seeded_db,
        user.id,
        lambda run: LLMRunContext(
            client, seeded_db, settings, run.id, clock, deadline=Deadline.after(clock, 240)
        ),
        clock=clock,
    )
    steps = writer.write(outcome.passed[0])
    findings["steps"] = report(
        "steps", calls(seeded_db, "recipe_steps"), schema_chars(RecipeSteps), f"status={steps.status}"
    )

    # 5. the probe: does Groq count the maximum completion against the minute? Wait for a full minute first.
    time.sleep(62)
    limit = ideas_ctx.pacer.minute_limit()
    probe = (
        {"role": "system", "content": "Reply with JSON only."},
        {"role": "user", "content": 'Reply with {"ok": true}.'},
    )
    try:
        answer = client.complete(
            LLMRequest(
                messages=probe,
                schema_name="Probe",
                json_schema=None,
                strict=False,
                max_completion_tokens=limit,  # prompt (~40) + this is just over the limit
                reasoning_effort=effort,
            )
        )
        findings["probe"] = {
            "max_completion_counted": False,
            "detail": f"accepted; prompt {answer.prompt_tokens}, completion {answer.completion_tokens}, "
            f"remaining after {answer.rate_limit.remaining_tokens} of {answer.rate_limit.limit_tokens}",
        }
    except LLMError as exc:
        findings["probe"] = {"max_completion_counted": True, "detail": str(exc)[:400]}
    print(f"\n[probe] limit={limit} {json.dumps(findings['probe'])}")
    print("\nFINDINGS " + json.dumps(findings))
    purposes = {r.purpose for r in seeded_db.scalars(select(LlmCall))}
    assert {"candidate_generation", "recipe_ideas", "recipe_steps"} <= purposes
    assert steps.status == "ready", steps.error


# ---------------- the ideas model: speed vs pass rate (2b.3b approval, P5) ----------------
COMPARE = os.environ.get("LLM_COMPARE_MODELS", "openai/gpt-oss-20b,openai/gpt-oss-120b").split(",")


def test_ideas_model_comparison(seeded_db):
    """The same ideas prompt on each model in LLM_COMPARE_MODELS, 2 runs each, alternating (each model has
    its own per-minute allowance): latency, tokens, and ideas asked / returned / passing the checks. About 4
    calls, ~20K tokens. Run alone: RUN_LIVE_LLM_TESTS=1 uv run pytest -m live_llm -s -k comparison"""
    settings = get_settings()
    user = current_user(seeded_db)
    clock = SystemClock()
    thighs = seeded_db.scalars(
        select(Ingredient.id).where(Ingredient.slug == "chicken-thigh-boneless-skinless")
    )
    add_lot(seeded_db, user.id, LotInput(thighs.one(), Decimal(700), "g", StorageLocation.FRIDGE))
    answers = CookAnswers(mode="now", slot=MealSlot.DINNER, goals=["high_protein"])
    user_settings = load_settings(seeded_db, user.id)
    query = answers_mod.resolve(answers, user_settings, datetime.now(ZoneInfo(user.timezone)))
    pool = load_pool(seeded_db, user.id, user_settings, query)
    resolver = IngredientResolver(seeded_db, user.id)
    req = meal_now_request(
        seeded_db,
        user.id,
        user_settings,
        query,
        pool,
        resolver=resolver,
        on_screen=[card["title"] for card in rank_pool(seeded_db, pool, query).cards],
    )
    rows: list[dict[str, Any]] = []
    for model in [m.strip() for _ in range(2) for m in COMPARE]:
        model_settings = settings.model_copy(update={"llm_model": model, "llm_ideas_model": None})
        client = make_client(model_settings)
        run = GenerationRun(user_id=user.id, purpose="meal_now", status="running")
        seeded_db.add(run)
        seeded_db.flush()
        ctx = LLMRunContext(
            client, seeded_db, model_settings, run.id, clock, deadline=Deadline.after(clock, 240)
        )
        started = time.monotonic()
        try:
            outcome = IdeaGenerator(seeded_db, user.id, ctx, resolver).generate(req, revise=False)
            error = None
        except LLMError as exc:
            outcome, error = None, str(exc)[:200]
        wall = round(time.monotonic() - started, 1)
        logged = list(
            seeded_db.scalars(select(LlmCall).where(LlmCall.generation_run_id == run.id).order_by(LlmCall.id))
        )
        ideas = (
            next(
                (c.error_detail or {}).get("ideas")
                for c in reversed(logged)
                if (c.error_detail or {}).get("ideas")
            )
            if logged
            else None
        )
        row = {
            "model": model,
            "wall_s": wall,
            "attempts": [
                (c.attempt, c.outcome, c.latency_ms, c.prompt_tokens, c.completion_tokens) for c in logged
            ],
            "tokens": sum((c.prompt_tokens or 0) + (c.completion_tokens or 0) for c in logged),
            "ideas": ideas,
            "passed": len(outcome.passed) if outcome else 0,
            "dropped": {k: v[:1] for k, v in (outcome.dropped if outcome else {}).items()},
            "error": error,
        }
        rows.append(row)
        print("\nCOMPARE " + json.dumps(row))
    print("\nCOMPARISON " + json.dumps(rows))
    assert sum(r["tokens"] for r in rows) < 40_000
