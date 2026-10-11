"""The ideas pass (planning/ideas.py, step 2b.3b): the count chosen from the token estimate, the idea checks,
short names mapping back, revision only when none pass, ideas saved without steps, and the reasoning effort on
every request (AC 4, 5)."""

import json

import pytest
from sqlalchemy import select

from app.db.models import GenerationRun, LlmCall, RecipeIngredient, RecipeVersion
from app.domain.enums import Equipment, MealSlot, RecipeMood
from app.llm.client import RateLimitInfo
from app.llm.errors import LLMProviderOutputError
from app.llm.fake import FakeLLMClient, response
from app.llm.pacing import RateState
from app.llm.structured import LLMRunContext
from app.planning.ideas import (
    MAX_IDEAS,
    MIN_IDEAS,
    PER_IDEA_TOKENS,
    REASONING_TOKENS,
    IdeaGenerator,
    IdeaRequest,
    IdeasDontFitError,
    size_call,
)
from app.planning.resolver import IngredientResolver
from app.schemas.llm_recipe import RecipeIdea
from app.services.ingredient_data import load_by_slug
from app.services.settings import current_user
from app.testing.llm import FakeClock, make_settings


def idea(title: str = "Garlic chicken spinach rice", **changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": title,
        "method": "Sear the chicken, simmer the rice, and wilt the spinach on top",
        "meal_slots": ["dinner"],
        "mood": "simple",
        "base_servings": 4,
        "active_minutes": 20,
        "total_minutes": 30,
        "equipment": ["stovetop"],
        "freezer_friendly": True,
        "ingredients": [
            {"name": "chicken thigh", "quantity": 600, "unit": "g", "role": "protein"},
            {"name": "white rice", "quantity": 300, "unit": "g", "role": "carb"},
            {"name": "spinach", "quantity": 200, "unit": "g", "role": "vegetable"},
            {"name": "olive oil", "quantity": 2, "unit": "tbsp", "role": "fat"},
            {"name": "salt", "quantity": 5, "unit": "g", "role": "seasoning"},
        ],
    }
    return {**base, **changes}


def request(**changes: object) -> IdeaRequest:
    values: dict[str, object] = {
        "slot": MealSlot.DINNER,
        "mood": RecipeMood.MEDIUM,
        "base_servings": 4,
        "equipment": frozenset({Equipment.STOVETOP, Equipment.OVEN}),
        "vocabulary": ("chicken thigh", "white rice", "spinach", "olive oil", "salt"),
        "never_use": ("beef and anything made from beef",),
        "max_active_minutes": 60,
    }
    return IdeaRequest(**{**values, **changes})  # type: ignore[arg-type]


def generator(session, client: FakeLLMClient, limit: int | None = None) -> IdeaGenerator:
    user = current_user(session)
    run = GenerationRun(user_id=user.id, purpose="meal_now", status="running")
    session.add(run)
    session.flush()
    rate = (
        RateState(RateLimitInfo(limit_tokens=limit, remaining_tokens=limit), 1000.0) if limit else RateState()
    )
    ctx = LLMRunContext(client, session, make_settings(), run.id, FakeClock(), rate=rate)
    return IdeaGenerator(session, user.id, ctx)


# ---------------- the count, from the token estimate ----------------
def test_the_count_is_the_largest_that_fits_the_minute():
    budget = 7600  # 95% of 8K
    assert size_call(1000, budget).count == MAX_IDEAS
    six = budget - (6 * PER_IDEA_TOKENS + REASONING_TOKENS)
    assert size_call(six, budget).count == 6
    assert size_call(six + 1, budget).count == MIN_IDEAS
    assert size_call(budget, budget) is None  # even 5 don't fit: no call
    for prompt in (1000, 3000, six):
        size = size_call(prompt, budget)
        assert size is not None and prompt + size.max_completion_tokens <= budget  # prompt + max ≤ 95%
        assert size.max_completion_tokens >= size.count * PER_IDEA_TOKENS + REASONING_TOKENS


def test_the_generator_sizes_the_call_from_its_calibrated_prompt(seeded_db):
    fake = FakeLLMClient([response({"ideas": [idea()]})])
    gen = generator(seeded_db, fake, limit=8000)
    size = gen.size(request())
    gen.generate(request())
    sent = fake.requests[0]
    assert sent.max_completion_tokens == size.max_completion_tokens
    assert f"Write {size.count} different dinner ideas" in sent.messages[1]["content"]
    assert size.prompt_tokens + sent.max_completion_tokens <= int(8000 * 0.95)
    with pytest.raises(IdeasDontFitError):
        generator(seeded_db, FakeLLMClient(), limit=1000).size(request())  # a tiny minute: no call at all


def test_the_estimate_is_calibrated_from_logged_calls(seeded_db):
    gen = generator(seeded_db, FakeLLMClient())
    first = gen.size(request()).prompt_tokens
    messages = [{"role": "user", "content": "x" * 4000}]  # about 1,000 raw tokens each
    for _ in range(5):
        seeded_db.add(
            LlmCall(
                purpose="recipe_ideas",
                provider="fake",
                model="fake-model",
                structured_mode="strict",
                prompt_version="recipe_ideas/1",
                attempt=1,
                request_messages=messages,
                outcome="ok",
                prompt_tokens=4000,  # the provider counted far more than characters suggest
                completion_tokens=500,
            )
        )
    seeded_db.flush()
    assert gen.size(request()).prompt_tokens > first  # the pacer and the daily guard now expect more


# ---------------- the checks ----------------
def test_a_passing_idea_is_saved_without_steps(seeded_db):
    fake = FakeLLMClient([response({"ideas": [idea()]})])
    outcome = generator(seeded_db, fake).generate(request())
    (version_id,) = outcome.created
    version = seeded_db.get(RecipeVersion, version_id)
    assert version.steps_status == "pending" and version.description.startswith("Sear the chicken")
    assert version.prompt_version == "recipe_ideas/1" and version.created_by == "llm"
    data = load_by_slug(seeded_db)
    lines = seeded_db.scalars(
        select(RecipeIngredient.ingredient_id).where(RecipeIngredient.recipe_version_id == version_id)
    ).all()
    assert data["chicken-thigh-boneless-skinless"].id in lines  # the short name mapped back exactly


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"meal_slots": ["breakfast"]}, "meal_slots must include 'dinner'"),
        ({"mood": "fancy"}, "mood must be medium or simpler"),
        ({"equipment": ["air_fryer"]}, "uses equipment that isn't available"),
        ({"title": "A cheap dinner"}, "cost"),
        ({"method": "Packed with protein, sear and simmer"}, "the app computes nutrients"),
    ],
)
def test_the_idea_checks(seeded_db, changes, expected):
    gen = generator(seeded_db, FakeLLMClient())
    validated, errors = gen.check(RecipeIdea.model_validate(idea(**changes)), request())
    assert validated is None and any(expected in e.lower() or expected in e for e in errors), errors


def test_quick_and_caps_are_the_requests_own_checks(seeded_db):
    gen = generator(seeded_db, FakeLLMClient())
    data = load_by_slug(seeded_db)
    slow = RecipeIdea.model_validate(idea(total_minutes=45))
    assert "total_minutes must be at most 30" in gen.check(slow, request(max_total_minutes=30))[1]
    capped = request(blocked={data["chicken-thigh-boneless-skinless"].id: "Chicken test cap"})
    errors = gen.check(RecipeIdea.model_validate(idea()), capped)[1]
    assert any("this week's allowance is used up" in e for e in errors)


def test_ideas_with_beef_or_held_items_fail_their_names(seeded_db):
    gen = generator(seeded_db, FakeLLMClient())
    beef = idea(
        ingredients=[
            {"name": "beef steak", "quantity": 600, "unit": "g", "role": "protein"},
            {"name": "white rice", "quantity": 300, "unit": "g", "role": "carb"},
        ]
    )
    assert any("excluded" in e for e in gen.check(RecipeIdea.model_validate(beef), request())[1])
    held = idea(
        ingredients=[
            {"name": "gelatin", "quantity": 10, "unit": "g", "role": "other"},
            {"name": "white rice", "quantity": 300, "unit": "g", "role": "carb"},
        ]
    )
    assert any("held" in e for e in gen.check(RecipeIdea.model_validate(held), request())[1])


# ---------------- revision ----------------
def test_revision_runs_only_when_no_idea_passes_and_sends_at_most_three(seeded_db):
    bad = [idea(f"Fancy {n}", mood="fancy") for n in range(5)]
    fake = FakeLLMClient([response({"ideas": bad}), response({"ideas": [idea()]})])
    outcome = generator(seeded_db, fake).generate(request())
    assert fake.calls == 2 and outcome.revised and len(outcome.created) == 1
    revision = fake.requests[1].messages[1]["content"]
    assert revision.count("Idea ") == 3 and "Idea 4" not in revision
    assert all(r.reasoning_effort == "low" for r in fake.requests)  # ideas, revision: the configured effort


def test_no_revision_when_one_passes_or_when_asked_not_to(seeded_db):
    fake = FakeLLMClient([response({"ideas": [idea("Fancy", mood="fancy"), idea()]})])
    assert not generator(seeded_db, fake).generate(request()).revised and fake.calls == 1
    background = FakeLLMClient([response({"ideas": [idea("Fancy", mood="fancy")]})])
    outcome = generator(seeded_db, background).generate(request(), revise=False)
    assert background.calls == 1 and outcome.created == [] and outcome.dropped


def test_the_same_idea_twice_is_saved_once(seeded_db):
    fake = FakeLLMClient([response({"ideas": [idea()]}), response({"ideas": [idea()]})])
    first = generator(seeded_db, fake).generate(request())
    second = generator(seeded_db, fake).generate(request())
    assert first.created and second.created == [] and second.passed == first.created


def test_the_prompt_uses_short_names_and_states_the_request(seeded_db):
    resolver = IngredientResolver(seeded_db, current_user(seeded_db).id)
    data = load_by_slug(seeded_db)
    assert resolver.short_name(data["chicken-thigh-boneless-skinless"].id) == "chicken thigh"
    assert resolver.short_name(data["flour-tortilla-small"].id) == "flour tortilla"
    fake = FakeLLMClient([response({"ideas": [idea()]})])
    generator(seeded_db, fake).generate(
        request(must_use=("spinach",), may_buy=("chickpeas",), hints=("favor protein-rich ingredients",))
    )
    text = fake.requests[0].messages[1]["content"]
    assert "use these (each idea uses at least one; as many as fit): spinach" in text
    assert "may also use these, which can be bought: chickpeas" in text
    assert "- favor protein-rich ingredients" in text and "NEVER USE: beef" in text
    assert fake.requests[0].json_schema is not None  # always a schema (strict or best effort)


def test_steps_rules_never_reach_the_ideas_prompt(seeded_db):
    fake = FakeLLMClient([response({"ideas": [idea()]})])
    generator(seeded_db, fake).generate(request())
    system = fake.requests[0].messages[0]["content"]
    assert "List every ingredient the cooking will use, including water, salt and oil" in system
    assert "doneness_check_for" not in system and "portioning step" not in system


# ---------------- a batch that fails as a whole keeps the ideas that validate ----------------
def test_a_provider_rejected_batch_keeps_its_valid_ideas_in_one_call(seeded_db):
    rejected = json.dumps({"ideas": [idea(), idea("Chicken rice pot", equipment=["stovetop", "pot"])]})
    fake = FakeLLMClient([LLMProviderOutputError("jsonschema: equipment enum", failed_output=rejected)])
    outcome = generator(seeded_db, fake).generate(request())
    assert (
        fake.calls == 1 and len(outcome.created) == 1
    )  # no retry: the valid idea is kept, the other dropped
    row = seeded_db.scalars(select(LlmCall).where(LlmCall.purpose == "recipe_ideas")).one()
    assert row.outcome == "ok" and row.error_detail["salvaged"] is True
    assert "jsonschema: equipment enum" in row.error_detail["errors"][0]


def test_one_malformed_idea_doesnt_sink_the_batch(seeded_db):
    broken = {k: v for k, v in idea("No method").items() if k != "method"}
    fake = FakeLLMClient([response({"ideas": [idea(), broken]})])
    outcome = generator(seeded_db, fake).generate(request())
    assert fake.calls == 1 and len(outcome.created) == 1


def test_a_batch_with_no_valid_idea_is_retried_with_the_errors(seeded_db):
    broken = {k: v for k, v in idea("No method").items() if k != "method"}
    fake = FakeLLMClient([response({"ideas": [broken]}), response({"ideas": [idea()]})])
    outcome = generator(seeded_db, fake).generate(request())
    assert fake.calls == 2 and len(outcome.created) == 1
    assert "method" in fake.requests[1].messages[-1]["content"]


def test_the_pass_rate_is_logged_on_the_call(seeded_db):
    """P7 (2b.3b approval): ideas asked for, returned and kept, on the ideas call's log row."""
    fake = FakeLLMClient([response({"ideas": [idea(), idea("Fancy", mood="fancy"), idea("Third")]})])
    gen = generator(seeded_db, fake, limit=8000)
    asked = gen.size(request()).count
    gen.generate(request())
    row = seeded_db.scalars(select(LlmCall).where(LlmCall.purpose == "recipe_ideas")).one()
    assert row.error_detail["ideas"] == {
        "asked": asked,
        "returned": 3,
        "kept": 2,
        "pass_rate": round(2 / asked, 3),
    }


def test_ideas_go_to_the_ideas_model_on_the_runs_own_call_cap(seeded_db):
    """P5: with LLM_IDEAS_MODEL set, the ideas call goes to that model and is logged under it; the run keeps
    one call cap, and everything else stays on LLM_MODEL."""
    user = current_user(seeded_db)
    run = GenerationRun(user_id=user.id, purpose="meal_now", status="running")
    seeded_db.add(run)
    seeded_db.flush()
    fake = FakeLLMClient([response({"ideas": [idea()]})])
    settings = make_settings(llm_ideas_model="ideas-model")
    ctx = LLMRunContext(fake, seeded_db, settings, run.id, FakeClock())
    gen = IdeaGenerator(seeded_db, user.id, ctx)
    gen.generate(request())
    assert [r.model for r in fake.requests] == ["ideas-model"]
    row = seeded_db.scalars(select(LlmCall).where(LlmCall.purpose == "recipe_ideas")).one()
    assert row.model == "ideas-model"
    assert gen.llm.calls is ctx.calls and ctx.client is fake
    plain = LLMRunContext(fake, seeded_db, make_settings(), run.id, FakeClock())
    assert plain.for_ideas() is plain
