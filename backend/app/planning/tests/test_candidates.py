"""The candidate pool (deliverable 10): seeds and saved versions first, the LLM only for uncovered slots."""

import json
from datetime import date

import pytest
from sqlalchemy import func, select

from app.db.models import GenerationRun, LlmCall, Recipe, RecipeVersion
from app.domain.enums import MealSlot
from app.llm.fake import FakeLLMClient, fixture_response, fixture_text, response
from app.llm.structured import LLMRunContext
from app.planning.candidates import CandidateGenerator, Gap, gap_analysis
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.schemas.plans import PlanRequest
from app.services.settings import current_user
from app.testing.llm import FakeClock, make_settings

WEEK = date(2026, 10, 12)
WITH_DRINK = {MealSlot.DINNER: 550, MealSlot.DRINK: 100}


def problem_for(session, slot_kcal=None):
    user = current_user(session)
    c = constraints_for(session, user.id, PlanRequest(week_start=WEEK, slot_kcal=slot_kcal or {}))
    return build_problem(session, user.id, c)


def generator(session, client, run=True, **settings):
    user = current_user(session)
    run_id = None
    if run:
        row = GenerationRun(user_id=user.id, purpose="weekly_plan", status="running")
        session.add(row)
        session.flush()
        run_id = row.id
    ctx = LLMRunContext(client, session, make_settings(**settings), run_id, FakeClock())
    return CandidateGenerator(session, user.id, ctx)


def llm_versions(session):
    return list(
        session.scalars(
            select(RecipeVersion)
            .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
            .where(Recipe.origin == "llm")
        )
    )


def test_seeds_cover_the_default_week_so_no_gaps(seeded_db):
    assert gap_analysis(problem_for(seeded_db)) == []


def test_a_drink_gap_makes_one_call_for_that_slot_only(seeded_db):
    p = problem_for(seeded_db, WITH_DRINK)
    gaps = gap_analysis(p)
    assert gaps == [Gap(MealSlot.DRINK, 2, "0 of 1 recipes needed")]
    client = FakeLLMClient([fixture_response("drinks_batch.json")])
    ids = generator(seeded_db, client).generate(p, gaps)
    assert client.calls == 1
    prompt = client.requests[0].messages[1]["content"]
    assert "drink recipes" in prompt and 'meal_slots must include "drink"' in prompt
    assert len(ids) == 2 and {v.title for v in llm_versions(seeded_db)} == {
        "Golden turmeric milk",
        "Cinnamon cocoa milk",
    }


def test_prompt_vocabulary_leaves_out_beef_held_and_pork_components(seeded_db):
    p = problem_for(seeded_db, WITH_DRINK)
    ctx = generator(seeded_db, FakeLLMClient()).context(p, gap_analysis(p)[0])
    vocabulary = set(ctx.vocabulary)
    assert "beef broth" not in vocabulary and "ground beef, 85% lean" not in vocabulary
    assert "gelatin, unflavored" not in vocabulary and "pepperoni" not in vocabulary  # held
    assert "bacon" not in vocabulary and "pork sausage, Italian" not in vocabulary  # never-favored, capped
    assert "lard" in vocabulary and "gelatin, pork-derived" in vocabulary  # trace pork stays
    never = " ".join(ctx.never_use)
    assert (
        "beef and anything made from beef" in never
        and "beef broth" in never
        and "gelatin, unflavored" in never
    )
    assert any("chapati or roti" in rule for rule in ctx.substitution_rules)


def test_one_invalid_recipe_gets_one_revision_call(seeded_db):
    p = problem_for(seeded_db, WITH_DRINK)
    revised = json.loads(fixture_text("drinks_batch.json"))["recipes"][1]
    client = FakeLLMClient([fixture_response("beef_broth_step.json"), response(revised)])
    gen = generator(seeded_db, client)
    ids = gen.generate(p, gap_analysis(p))
    assert client.calls == 2 and len(ids) == 2
    revision = client.requests[1].messages[1]["content"]
    assert "excluded (beef)" in revision and "Cinnamon cocoa milk" in revision
    calls = list(seeded_db.scalars(select(LlmCall).order_by(LlmCall.id)))
    assert [c.purpose for c in calls] == ["candidate_generation", "recipe_revision"]
    assert calls[1].parent_call_id == calls[0].id
    assert "Cinnamon cocoa milk" in calls[0].error_detail["recipe_issues"]


def test_a_recipe_still_invalid_after_revision_is_dropped(seeded_db):
    p = problem_for(seeded_db, WITH_DRINK)
    bad = json.loads(fixture_text("beef_broth_step.json"))["recipes"][1]
    client = FakeLLMClient([fixture_response("beef_broth_step.json")], default=response(bad))
    gen = generator(seeded_db, client)
    ids = gen.generate(p, gap_analysis(p))
    assert len(ids) == 1 and client.calls == 1 + 3
    assert gen.dropped and gen.dropped[0][0] == "Cinnamon cocoa milk"


def test_same_recipe_twice_is_deduplicated(seeded_db):
    p = problem_for(seeded_db, WITH_DRINK)
    first = generator(seeded_db, FakeLLMClient([fixture_response("drinks_batch.json")])).generate(
        p, gap_analysis(p)
    )
    count = seeded_db.scalar(select(func.count()).select_from(RecipeVersion))
    second = generator(seeded_db, FakeLLMClient([fixture_response("drinks_batch.json")])).generate(
        p, [Gap(MealSlot.DRINK, 2, "again")]
    )
    assert second == first
    assert seeded_db.scalar(select(func.count()).select_from(RecipeVersion)) == count


def test_generated_recipes_keep_their_provenance(seeded_db):
    p = problem_for(seeded_db, WITH_DRINK)
    gen = generator(seeded_db, FakeLLMClient([fixture_response("drinks_batch.json")]))
    gen.generate(p, gap_analysis(p))
    for version in llm_versions(seeded_db):
        recipe = seeded_db.get(Recipe, version.recipe_id)
        assert recipe.origin == "llm" and recipe.default_version_id == version.id
        assert version.created_by == "llm" and not version.is_draft and version.version_number == 1
        assert version.prompt_version == "candidate_generation/1"
        assert version.generation_run_id == gen.llm.run_id
        call = seeded_db.get(LlmCall, version.source_llm_call_id)
        assert call is not None and call.outcome == "ok" and call.purpose == "candidate_generation"


def test_a_truncated_batch_is_halved(seeded_db):
    p = problem_for(seeded_db, WITH_DRINK)
    single = {"recipes": [json.loads(fixture_text("drink_single.json"))]}
    client = FakeLLMClient([fixture_response("truncated.txt", finish_reason="length"), response(single)])
    ids = generator(seeded_db, client).generate(p, gap_analysis(p))
    assert client.calls == 2 and len(ids) == 1
    assert "Write 2 different drink recipes" in client.requests[0].messages[1]["content"]
    assert "Write 1 different drink recipe " in client.requests[1].messages[1]["content"]


@pytest.mark.parametrize("mode", ["strict", "best_effort"])
def test_unresolved_names_feed_the_suggestions_queue(seeded_db, mode):
    p = problem_for(seeded_db, WITH_DRINK)
    batch = json.loads(fixture_text("drinks_batch.json"))
    batch["recipes"][0]["ingredients"][1]["name"] = "saffron threads"
    fixed = json.loads(fixture_text("drinks_batch.json"))["recipes"][0]
    client = FakeLLMClient([response(batch), response(fixed)])
    generator(seeded_db, client, llm_structured_mode=mode).generate(p, gap_analysis(p))
    first = seeded_db.scalars(select(LlmCall).order_by(LlmCall.id)).first()
    assert first is not None and first.error_detail["unresolved_ingredients"] == ["saffron threads"]
    assert first.structured_mode == mode
