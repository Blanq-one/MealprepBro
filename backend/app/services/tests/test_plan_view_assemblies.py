"""The plan view's read side for smart prep (step 2b.7, FLOW_SPEC §19.10; X8): an assembled meal draws
portions from several prep batches, a prep batch stops at a state, and eating days carry finish tasks.
2b.11's solver fills these tables; here a dish plan is planned for real, then one meal is turned into an
assembly of prep batches the way 2b.11 will write it. Also the batch view's "where each portion goes" (F23)
and the plan's own notes behind the one Prep notes row."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.home import today_card
from app.db.models import (
    AssemblyComponent,
    MealPlan,
    PlanBatchIngredient,
    PlanCookBatch,
    PlanFinishTask,
    PlanMeal,
    PlanMealComponent,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
)
from app.domain.enums import MealSlot
from app.planning.orchestrator import Orchestrator
from app.schemas.plans import PlanRequest
from app.services.plans import plan_summary
from app.services.settings import current_user
from app.testing.llm import FakeClock, make_settings

WEEK = date(2026, 10, 12)  # a Monday
TUE, WED = WEEK + timedelta(days=1), WEEK + timedelta(days=2)


def item_version(session: Session, title: str) -> RecipeVersion:
    """A seed prep item's default version (a dish can share its title: the stir-fry)."""
    version = session.scalars(
        select(RecipeVersion)
        .join(Recipe, Recipe.default_version_id == RecipeVersion.id)
        .where(Recipe.title == title, RecipeVersion.kind == "prep_item")
    ).one()
    return version


def assembly_of(session: Session, *items: str) -> RecipeVersion:
    """The seed assembly made of exactly these prep items."""
    wanted = {item_version(session, t).recipe_id for t in items}
    for version in session.scalars(select(RecipeVersion).where(RecipeVersion.kind == "assembly")):
        parts = set(
            session.scalars(
                select(AssemblyComponent.component_recipe_id).where(
                    AssemblyComponent.assembly_version_id == version.id
                )
            )
        )
        if parts == wanted:
            return version
    raise AssertionError(f"no seed assembly of {items}")


def prep_batch(
    session: Session,
    plan_id: int,
    title: str,
    cook_on: date,
    portions: int,
    *,
    stop: tuple[int, str] | None = None,
) -> PlanCookBatch:
    """A prep batch with its practical lines (the item's lines scaled to its portions), as 2b.11 saves one."""
    version = item_version(session, title)
    scale = Decimal(portions) / version.base_servings
    batch = PlanCookBatch(
        meal_plan_id=plan_id,
        recipe_version_id=version.id,
        cook_on=cook_on,
        portions=portions,
        portion_size="normal",
        portion_multiplier=Decimal(1),
        scale_factor=scale,
        planned_minutes=30,
        stop_stage=stop[0] if stop else None,
        stop_state=stop[1] if stop else None,
    )
    session.add(batch)
    session.flush()
    for line in session.scalars(
        select(RecipeIngredient).where(RecipeIngredient.recipe_version_id == version.id)
    ):
        session.add(
            PlanBatchIngredient(
                cook_batch_id=batch.id,
                recipe_ingredient_id=line.id,
                ingredient_id=line.ingredient_id,
                quantity=line.quantity * scale,
                unit=line.unit,
            )
        )
    session.flush()
    return batch


def assemble(
    session: Session,
    meal: PlanMeal,
    assembly: RecipeVersion,
    draws: list[tuple[PlanCookBatch, str, bool, int | None]],
) -> None:
    """Turn a dish meal into an assembled one: (batch, portions per person, from the freezer, finish task)."""
    meal.cook_batch_id = None
    meal.assembly_version_id = assembly.id
    for batch, portions, frozen, task in draws:
        session.add(
            PlanMealComponent(
                plan_meal_id=meal.id,
                cook_batch_id=batch.id,
                portions=Decimal(portions),
                from_freezer=frozen,
                finish_task_id=task,
            )
        )
    session.flush()


@pytest.fixture
def smart_plan(seeded_db: Session) -> dict[str, object]:
    """A 3-day dish plan; then Tuesday's dinner is chicken curry with rice from prep batches cooked Monday,
    and Wednesday's is the tandoori drumsticks, marinated Monday and roasted Wednesday, with rice."""
    user = current_user(seeded_db)
    out = Orchestrator(seeded_db, user.id, llm_client=None, settings=make_settings(), clock=FakeClock()).run(
        PlanRequest(week_start=WEEK, days=3, allow_llm=False)
    )
    assert out.status == "succeeded", out.error
    plan_id = out.plan_id
    assert plan_id is not None
    meals = {
        (m.eat_on, m.slot): m
        for m in seeded_db.scalars(select(PlanMeal).where(PlanMeal.meal_plan_id == plan_id))
    }
    curry = prep_batch(seeded_db, plan_id, "Chicken curry", WEEK, 4)
    rice = prep_batch(seeded_db, plan_id, "Plain rice", WEEK, 4)
    tandoori = prep_batch(seeded_db, plan_id, "Tandoori drumsticks", WEEK, 4, stop=(1, "marinated"))
    roast = PlanFinishTask(
        meal_plan_id=plan_id,
        day=WED,
        cook_batch_id=tandoori.id,
        kind="stage",
        portions=Decimal(1),
        hands_on_minutes=5,
        hands_off_minutes=25,
        equipment="oven",
    )
    seeded_db.add(roast)
    seeded_db.flush()
    assemble(
        seeded_db,
        meals[(TUE, "dinner")],
        assembly_of(seeded_db, "Chicken curry", "Plain rice"),
        [(curry, "1", False, None), (rice, "1", False, None)],
    )
    tandoori_rice = assembly_of(seeded_db, "Tandoori drumsticks", "Plain rice", "Cucumber raita")
    raita = prep_batch(seeded_db, plan_id, "Cucumber raita", WEEK, 4)
    assemble(
        seeded_db,
        meals[(WED, "dinner")],
        tandoori_rice,
        [(tandoori, "1", False, roast.id), (rice, "1", False, None), (raita, "1", False, None)],
    )
    plan = seeded_db.get(MealPlan, plan_id)
    assert plan is not None
    plan.validation_report = {**plan.validation_report, "notes": ["Left out Spicy beef chili: uses beef"]}
    seeded_db.flush()
    return {"plan_id": plan_id, "user_id": user.id, "curry": curry, "tandoori": tandoori, "roast": roast}


def test_an_assembled_meal_lists_its_items_their_sources_and_its_instruction(seeded_db, smart_plan):
    summary = plan_summary(seeded_db, smart_plan["user_id"], smart_plan["plan_id"])
    tuesday = next(d for d in summary.days if d.day == TUE)
    meal = next(m for m in tuesday.meals if m.slot == "dinner")
    assert meal.kind == "assembly" and meal.cook_batch_id is None
    assert meal.title.startswith("Chicken curry with")
    assert [c.label for c in meal.components] == ["chicken curry", "rice"]
    assert {c.portions_display for c in meal.components} == {"1 portion"}
    assert meal.source_display == "From the fridge, cooked Mon 12"
    assert meal.instruction == "Reheat 1 portion chicken curry and 1 portion rice to 165°F."
    assert meal.protein_g > 0  # its items' rounded batches, per person
    # every other meal is still a dish meal from one batch
    others = [m for d in summary.days for m in d.meals if m.kind == "dish"]
    assert others and all(m.cook_batch_id is not None and not m.components for m in others)
    assert sum(1 for d in summary.days for m in d.meals if m.kind == "assembly") == 2


def test_a_prep_batch_stops_at_its_state_and_finishes_on_its_eating_day(seeded_db, smart_plan):
    summary = plan_summary(seeded_db, smart_plan["user_id"], smart_plan["plan_id"])
    tandoori = next(b for b in summary.batches if b.id == smart_plan["tandoori"].id)
    assert tandoori.kind == "prep_item" and tandoori.stop_state == "marinated"
    assert tandoori.stop_display == "marinate only"
    assert tandoori.uses_display == "Wed dinner"
    monday = summary.days[0]
    assert "Tandoori drumsticks, marinate only (4 portions)" in monday.cook_note
    wednesday = next(d for d in summary.days if d.day == WED)
    (task,) = wednesday.finish_tasks
    assert task.kind == "stage" and task.time_display == "30 min, 5 hands-on"
    assert task.text.startswith("Roast the marinated tandoori drumsticks (1 portion): ")
    assert "until it reaches 165°F" in task.text  # the safe temperature, from the food-safety table
    dinner = next(m for m in wednesday.meals if m.slot == "dinner")
    assert dinner.instruction is not None and dinner.instruction.startswith(
        "Roast the marinated tandoori drumsticks"
    )
    assert "Reheat 1 portion rice to 165°F." in dinner.instruction


def test_each_batch_says_where_its_portions_go(seeded_db, smart_plan):
    """F23: every batch lists the meals its portions go to, in meal order, a prep batch through its draws."""
    summary = plan_summary(seeded_db, smart_plan["user_id"], smart_plan["plan_id"])
    order = list(MealSlot)
    for batch in summary.batches:
        fed = {
            (m.eat_on, m.slot)
            for d in summary.days
            for m in d.meals
            if m.cook_batch_id == batch.id or any(c.cook_batch_id == batch.id for c in m.components)
        }
        assert [(u.eat_on, u.slot) for u in batch.uses] == sorted(
            fed, key=lambda f: (f[0], order.index(f[1]))
        )
        assert batch.uses_display.startswith(", ".join(u.label for u in batch.uses))
    rice = next(b for b in summary.batches if b.title == "Plain rice")
    assert rice.uses_display == "Tue dinner, Wed dinner"
    curry = next(b for b in summary.batches if b.id == smart_plan["curry"].id)
    assert curry.uses_display == "Tue dinner"


def test_the_plans_own_notes_sit_behind_the_one_prep_notes_row(seeded_db, smart_plan):
    summary = plan_summary(seeded_db, smart_plan["user_id"], smart_plan["plan_id"])
    assert summary.prep_notes is not None
    about = [i.text for i in summary.prep_notes.items if i.kind == "about"]
    assert "Left out Spicy beef chili: uses beef" in about
    assert summary.prep_notes.display.endswith("About this plan")


def test_the_batch_page_of_a_prep_batch_says_when_it_is_prepped_and_finished(client, seeded_db, smart_plan):
    batch = client.get(f"/api/v1/cook-batches/{smart_plan['tandoori'].id}").json()
    assert batch["in_plan"] == "In this plan: marinate on Mon 12, roast on Wed 14."
    (meal,) = batch["meals"]
    assert meal["kind"] == "assembly" and meal["title"].startswith("Tandoori drumsticks")


def test_the_today_card_shows_an_assembled_meal(seeded_db, smart_plan):
    plan = seeded_db.get(MealPlan, smart_plan["plan_id"])
    plan.status = "active"
    seeded_db.flush()
    card = today_card(seeded_db, smart_plan["user_id"], TUE)
    assert card is not None and card.state == "today"
    dinner = next(m for m in card.meals if m.slot == "dinner")
    assert dinner.cook_batch_id is None and dinner.title.startswith("Chicken curry with")
