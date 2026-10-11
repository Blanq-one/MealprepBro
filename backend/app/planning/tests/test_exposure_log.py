"""Candidate-exposure log (Phase 2, AC 2.9): every succeeded plan run writes one plan_candidate row per recipe
offered to the solver or filtered out, with `selected` and `filtered_reason` right."""

from collections import Counter
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.models import (
    Ingredient,
    PlanCandidate,
    PlanCookBatch,
    Recipe,
    RecipeIngredient,
    RecipeStep,
    RecipeVersion,
)
from app.domain.enums import MealSlot
from app.llm.fake import FakeLLMClient, fixture_response
from app.planning.exposure import filtered_reason
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.planning.orchestrator import Orchestrator
from app.planning.problem import ExcludedRecipe
from app.schemas.plans import DayOverride, PlanRequest
from app.services.settings import current_user, load_settings, save_settings
from app.testing.llm import FakeClock, make_settings

WEEK = date(2026, 10, 12)
DAYS = 3  # small enough that every solve reaches its gap quickly


def run(session, client=None, **request):
    user = current_user(session)
    o = Orchestrator(session, user.id, llm_client=client, settings=make_settings(), clock=FakeClock())
    return o.run(PlanRequest(week_start=WEEK, days=DAYS, **request))


def rows(session, run_id) -> list[PlanCandidate]:
    return list(session.scalars(select(PlanCandidate).where(PlanCandidate.generation_run_id == run_id)))


def slug_id(session, slug):
    return session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()


def variant(session, title: str, new_title: str, extra_slug: str) -> int:
    """Your own version of a seed recipe with one more ingredient (stored like an edited recipe)."""
    user = current_user(session)
    base = session.scalars(select(RecipeVersion).where(RecipeVersion.title == title)).first()
    recipe = Recipe(user_id=user.id, title=new_title, origin="user")
    session.add(recipe)
    session.flush()
    copy = RecipeVersion(
        recipe_id=recipe.id,
        version_number=1,
        created_by="user",
        title=new_title,
        description=base.description,
        meal_slots=list(base.meal_slots),
        mood=base.mood,
        cuisine=base.cuisine,
        flavor_tags=list(base.flavor_tags),
        base_servings=base.base_servings,
        active_minutes=base.active_minutes,
        total_minutes=base.total_minutes,
        equipment=list(base.equipment),
        freezer_friendly=base.freezer_friendly,
        content_hash=f"test-{new_title}",
    )
    session.add(copy)
    session.flush()
    lines = session.scalars(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_version_id == base.id)
        .order_by(RecipeIngredient.position)
    ).all()
    for line in lines:
        session.add(
            RecipeIngredient(
                recipe_version_id=copy.id,
                position=line.position,
                ingredient_id=line.ingredient_id,
                quantity=line.quantity,
                unit=line.unit,
                authored_quantity=line.authored_quantity,
                authored_unit=line.authored_unit,
                preparation=line.preparation,
                role=line.role,
                component=line.component,
                is_optional=line.is_optional,
            )
        )
    session.add(
        RecipeIngredient(
            recipe_version_id=copy.id,
            position=len(lines) + 1,
            ingredient_id=slug_id(session, extra_slug),
            quantity=Decimal(10),
            unit="g",
            authored_quantity=Decimal(10),
            authored_unit="g",
            role="other",
        )
    )
    for step in session.scalars(select(RecipeStep).where(RecipeStep.recipe_version_id == base.id)):
        session.add(
            RecipeStep(
                recipe_version_id=copy.id,
                position=step.position,
                section=step.section,
                text=step.text,
                duration_minutes=step.duration_minutes,
                appliance_temp_f=step.appliance_temp_f,
                doneness_check_ingredient_id=step.doneness_check_ingredient_id,
            )
        )
    session.flush()
    recipe.default_version_id = copy.id
    session.flush()
    return copy.id


def test_a_cold_start_plan_logs_every_seed_candidate_with_its_selection(seeded_db):
    out = run(seeded_db, FakeLLMClient.failing())
    assert out.status == "succeeded" and out.llm_calls == 0
    logged = rows(seeded_db, out.run_id)
    offered = [r for r in logged if r.filtered_reason is None]
    # every seed candidate of the week is logged (the solver may see a shortlist: planning/shortlist.py)
    user = current_user(seeded_db)
    week = constraints_for(seeded_db, user.id, PlanRequest(week_start=WEEK, days=DAYS))
    candidates = build_problem(seeded_db, user.id, week).candidates
    assert len(offered) == len(candidates) and {r.source for r in logged} == {"seed"}
    assert all(r.meal_plan_id == out.plan_id for r in logged)
    batches = seeded_db.scalars(select(PlanCookBatch).where(PlanCookBatch.meal_plan_id == out.plan_id)).all()
    portions = Counter()
    for b in batches:
        portions[b.recipe_version_id] += b.portions
    for r in logged:
        assert r.selected == (r.recipe_version_id in portions)
        assert r.portions_selected == portions.get(r.recipe_version_id, 0)
    for r in offered:
        assert r.heuristic_score is not None and "cost" in r.score_components
        assert r.features["energy_kcal"] and r.features["origin"] == "seed" and r.eligible_slots


def test_held_and_capped_out_recipes_are_logged_with_their_reason(seeded_db):
    held = variant(
        seeded_db, "Double chocolate protein pudding", "Pudding with gelatin", "gelatin-unflavored"
    )
    capped = variant(seeded_db, "Everyday chicken curry gravy", "Curry with bacon", "bacon")
    user = current_user(seeded_db)
    settings = load_settings(seeded_db, user.id)
    caps = [c.model_copy(update={"max_meals_per_week": 0}) for c in settings.frequency_caps]
    assert caps  # the default pork cap
    save_settings(seeded_db, user.id, settings.model_copy(update={"frequency_caps": caps}))
    out = run(seeded_db)
    assert out.status == "succeeded", out.error
    by_version = {r.recipe_version_id: r for r in rows(seeded_db, out.run_id)}
    assert by_version[held].filtered_reason == "held" and not by_version[held].selected
    assert by_version[capped].filtered_reason == "frequency_cap" and not by_version[capped].selected
    assert by_version[held].source == "user_version" and by_version[held].heuristic_score is None
    assert any("frequency cap" in r for r in by_version[capped].features["reasons"])


def test_with_a_cap_above_zero_a_pork_recipe_is_offered_and_logged_as_never_favored(seeded_db):
    pork = variant(seeded_db, "Everyday chicken curry gravy", "Curry with bacon", "bacon")
    out = run(seeded_db)
    logged = {r.recipe_version_id: r for r in rows(seeded_db, out.run_id)}
    assert logged[pork].filtered_reason is None
    assert logged[pork].features["never_favored"] is True and "never_favored" in logged[pork].score_components
    assert "primary" not in logged[pork].score_components  # no nutrition bonus for a capped item


def test_recipes_generated_in_the_run_are_logged_as_new(seeded_db):
    client = FakeLLMClient([fixture_response("drinks_batch.json")])
    out = run(
        seeded_db,
        client,
        slot_kcal={MealSlot.DINNER: 550, MealSlot.DRINK: 100},
        day_overrides=[DayOverride(day=WEEK, cook_minutes=60)],
    )
    assert out.status == "succeeded", out.error
    new = [r for r in rows(seeded_db, out.run_id) if r.source == "llm_new"]
    assert new and all("drink" in r.eligible_slots for r in new)


def test_a_run_without_a_plan_logs_nothing(seeded_db):
    out = run(seeded_db, mode="inventory", topup_cents=0)  # an empty fridge: infeasible
    assert out.status == "infeasible" and rows(seeded_db, out.run_id) == []


def test_the_first_reason_wins_by_priority():
    def excluded(*codes):
        return ExcludedRecipe(1, "x", frozenset(), ("r",), codes=codes)

    assert filtered_reason(excluded("time", "held")) == "held"
    assert filtered_reason(excluded("equipment", "unpriced")) == "equipment"
    assert filtered_reason(excluded()) == "excluded"
