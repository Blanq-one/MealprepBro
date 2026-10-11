"""Cook this (E3, FLOW_SPEC C8, change F8): one recipe at N portions saved as a one-meal plan for today, so
inventory deduction (Mark cooked), open packages, the Buy first checklist and history work exactly as for
planned batches.

No solver: one meal has nothing to coordinate. The batch is rounded by the planner's own rounding, the grocery
list and money come from the planner's code, and the plan validator checks it in its "single" scope (one meal
isn't a day, so the day and week calorie limits and the protein target are skipped; everything else runs). It
is saved with kind "single", so it never becomes the current plan. When it comes from a meal-now search, that
search's pantry choices apply and its exposure row is marked selected.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.cook.answers import slot_from_clock
from app.cook.caps import meals_this_week, used_up
from app.cook.ideas import LLMAccess, wait_seconds
from app.cook.pool import store_ids
from app.cook.search import get_search, local_now
from app.db.models import (
    AppUser,
    CookSearch,
    GroceryList,
    GroceryListItem,
    InventoryItem,
    PlanCandidate,
    PlanCookBatch,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
)
from app.domain.enums import MealSlot, PlanningMode, PortionSize, RecipeMood
from app.domain.exclusions import ExclusionStatus
from app.domain.nutrition import kcal_display
from app.llm.pacing import Deadline
from app.planning.constraint_builder import DietInputs
from app.planning.costing import cost_summary
from app.planning.grocery_list import build_grocery
from app.planning.inputs import diet_inputs
from app.planning.loader import build_problem
from app.planning.perishables import freeze_instructions
from app.planning.persistence import SINGLE, save_plan
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import plan_totals
from app.planning.reference import load_reference
from app.planning.rounded import RoundedMeal, RoundedPlan
from app.planning.rounding import round_batch
from app.planning.solver.model import SolvedBatch
from app.planning.steps import StepsWriter
from app.schemas.constraints import (
    CalorieTolerance,
    DaySpec,
    PlanConstraints,
    ResolvedFrequencyCap,
    SlotTarget,
)
from app.schemas.cook import CookAnswers, CookMealIn, CookMealOut
from app.schemas.settings import UserSettings
from app.services import plans as plan_service
from app.services.errors import ConflictError
from app.services.recipes import RecipeNotFoundError
from app.services.settings import load_settings

NO_TIME_LIMIT = 600  # DaySpec's maximum: without Quick, any hands-on time fits one meal
MAX_SLOT_KCAL = 3000
_PROTEIN = Decimal("0.1")


class CookThisError(ValueError):
    """The recipe can't be cooked as asked (a diet rule, this week's cap); the message says why (422)."""


class StepsNotReadyError(ConflictError):
    """A new idea whose steps couldn't be written just now (409; `retry_after_s` during a rate-limit
    pause)."""

    def __init__(self, message: str, *, retry_after_s: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s
        self.code = code


STEPS_TIME_BUDGET_S = (
    90.0  # Cook this waits this long for an idea's steps (the recipe page writes them first)
)


def _version(session: Session, user_id: int, version_id: int) -> tuple[Recipe, RecipeVersion]:
    row = session.execute(
        select(Recipe, RecipeVersion)
        .join(RecipeVersion, RecipeVersion.recipe_id == Recipe.id)
        .where(RecipeVersion.id == version_id)
    ).first()
    if row is None or row[0].user_id != user_id or row[0].archived_at is not None:
        raise RecipeNotFoundError(f"recipe version {version_id} not found")
    return row[0], row[1]


def _existing(session: Session, search: CookSearch, version_id: int) -> PlanCookBatch | None:
    """This search's one-meal plan for this recipe, when Cook this was tapped before and it isn't cooked
    yet."""
    if search.meal_plan_id is None:
        return None
    return session.scalars(
        select(PlanCookBatch).where(
            PlanCookBatch.meal_plan_id == search.meal_plan_id,
            PlanCookBatch.recipe_version_id == version_id,
            PlanCookBatch.status == "planned",
        )
    ).first()


def choose_slot(asked: MealSlot | None, recipe_slots: list[str], clock: MealSlot) -> MealSlot:
    """The meal you asked for, else the clock's, when the recipe is for it; else the recipe's first meal."""
    for slot in (asked, clock):
        if slot is not None and slot.value in recipe_slots:
            return slot
    return next(s for s in MealSlot if s.value in recipe_slots)


def constraints_for_meal(
    settings: UserSettings,
    diet: DietInputs,
    stores: tuple[int, ...],
    *,
    off_lot_ids: frozenset[int] = frozenset(),
    today: date,
    slot: MealSlot,
    portions: int,
    mood: RecipeMood,
    minutes: int,
    answers: CookAnswers | None,
) -> PlanConstraints:
    """One day, one meal, `portions` people eating it together (household_size), in shop mode with no limit:
    whatever you don't have becomes the Buy first list. "Have it" extras count as yours for this meal (never
    bought, never listed, not deducted); pantry items you turned off aren't used."""
    allocations = {a.slot: a.kcal for a in settings.slot_allocations}
    kcal = allocations.get(slot) or min(MAX_SLOT_KCAL, settings.daily_kcal_target)
    have = (
        frozenset(e.ingredient_id for e in answers.extras if e.status == "have") if answers else frozenset()
    )
    off = frozenset(t.ingredient_id for t in answers.pantry if not t.include) if answers else frozenset()
    excluded = frozenset(i for i, s in diet.statuses.items() if s is not ExclusionStatus.ALLOWED)
    held = frozenset(i for i, s in diet.statuses.items() if s is ExclusionStatus.HELD)
    capped_out = (
        frozenset(i for cap in diet.caps if cap.max_meals_per_week == 0 for i in cap.member_ids) & excluded
    )
    return PlanConstraints(
        week_start=today,
        days=(
            DaySpec(
                day=today,
                slots=(slot,),
                is_cook_day=True,
                cook_minutes_available=minutes,
                mood=mood,
                kcal_target=kcal,
            ),
        ),
        calorie_mode=settings.calorie_mode,
        daily_kcal_target=settings.daily_kcal_target,
        weekly_kcal_target=kcal,
        tolerance=CalorieTolerance(
            weekly_under_pct=settings.weekly_under_pct,
            daily_under_pct=settings.daily_under_pct,
            daily_band_kcal=settings.daily_band_kcal,
        ),
        slot_targets=(SlotTarget(slot=slot, kcal=kcal),),
        daily_protein_target_g=settings.daily_protein_target_g,
        nutrition_priority=settings.nutrition_priority,
        secondary_priority=settings.secondary_priority,
        grocery_mode=settings.grocery_mode,
        planning_mode=PlanningMode.SHOP,
        purchase_limit_cents=None,
        default_portion_size=settings.default_portion_size,
        portion_nudge_pct=0,
        equipment=frozenset(settings.equipment),
        leftover_fridge_days=settings.leftover_fridge_days,
        store_ids=stores,
        store_split_min_savings_cents=settings.store_split_min_savings_cents,
        excluded_diet_tags=frozenset(settings.excluded_diet_tags),
        excluded_ingredient_ids=excluded,
        held_ingredient_ids=held,
        capped_out_ingredient_ids=capped_out,
        frequency_caps=tuple(
            ResolvedFrequencyCap(
                label=cap.label,
                member_ingredient_ids=cap.member_ids,
                max_meals_per_week=cap.max_meals_per_week,
                never_favor=cap.never_favor,
            )
            for cap in diet.caps
            if cap.max_meals_per_week > 0
        ),
        disliked_ingredient_ids=diet.disliked_ids - excluded,
        favorite_recipe_ids=diet.favorite_recipe_ids,
        always_have_ingredient_ids=diet.always_have_ids | have,
        lots_off_ingredient_ids=off - have,
        lots_off_lot_ids=off_lot_ids,
        household_size=portions,
        region_code=settings.region_code,
    )


def build_meal_plan(
    session: Session,
    user_id: int,
    c: PlanConstraints,
    recipe: Recipe,
    version: RecipeVersion,
) -> RoundedPlan:
    problem = build_problem(session, user_id, c, pairs=[(recipe, version)])
    if problem.excluded:
        raise CookThisError(f"Can't cook {version.title}: " + "; ".join(problem.excluded[0].reasons))
    if not problem.candidates:
        raise CookThisError(f"{version.title} isn't a {c.slot_targets[0].slot.value} recipe")
    day, slot = c.days[0].day, c.slot_targets[0].slot
    batch = round_batch(
        problem, SolvedBatch(version.id, day, c.default_portion_size, Decimal(1), c.household_size)
    )
    per = batch.per_portion
    meals = (
        RoundedMeal(
            eat_on=day,
            slot=slot,
            batch_index=0,
            from_freezer=False,
            kcal=kcal_display(per.get("energy_kcal", Decimal(0))),
            protein_g=per.get("protein_g", Decimal(0)).quantize(_PROTEIN, ROUND_HALF_UP),
        ),
    )
    grocery = build_grocery(c, [batch], problem.ingredients)
    costs, leftovers = cost_summary(c, [batch], grocery, problem.ingredients, meals)
    return RoundedPlan(
        constraints=c,
        batches=(batch,),
        meals=meals,
        grocery=grocery,
        totals=plan_totals(problem, [batch], meals, grocery),
        solver_status="single",
        solver_objective=0.0,
        costs=costs,
        leftovers=leftovers,
        freeze=freeze_instructions(c, [batch], grocery, problem.ingredients),
    )


def _out(session: Session, user_id: int, plan_id: int, batch_id: int, created: bool) -> CookMealOut:
    glist = session.scalars(select(GroceryList).where(GroceryList.meal_plan_id == plan_id)).one()
    kinds = [
        (item.reason or {}).get("kind", "buy")
        for item in session.scalars(
            select(GroceryListItem).where(GroceryListItem.grocery_list_id == glist.id)
        )
    ]
    return CookMealOut(
        plan_id=plan_id,
        batch_id=batch_id,
        grocery_list_id=glist.id,
        buy_first=any(kind in ("buy", "unpriced") for kind in kinds),
        created=created,
        plan=plan_service.plan_summary(session, user_id, plan_id),
    )


def ensure_steps(session: Session, user: AppUser, version: RecipeVersion, access: LLMAccess | None) -> None:
    """A new idea gets its steps before it is cooked (step 2b.3b deliverable 6); 0 calls when they exist."""
    if version.steps_status is None:
        return
    client, reason = access.client() if access is not None else (None, "no LLM client is configured")
    if client is None or access is None:
        raise StepsNotReadyError(
            f"The steps for {version.title} aren't written yet ({reason}).", code="llm_config"
        )
    deadline = Deadline.after(access.clock, STEPS_TIME_BUDGET_S)
    outcome = StepsWriter(
        session,
        user.id,
        lambda run: access.context(session, client, run.id, deadline=deadline),
        clock=access.clock,
    ).write(version.id)
    if outcome.status == "waiting":
        raise StepsNotReadyError(
            f"The steps for {version.title} need a short wait.",
            retry_after_s=wait_seconds(outcome.retry_after_s),
            code="llm_wait_too_long",
        )
    if outcome.status != "ready":
        raise StepsNotReadyError(
            f"I couldn't write the steps for {version.title} just now.",
            code=outcome.error.code if outcome.error else None,
        )
    session.refresh(version)


def cook_meal(
    session: Session,
    user: AppUser,
    body: CookMealIn,
    *,
    now: datetime | None = None,
    access: LLMAccess | None = None,
) -> CookMealOut:
    """`now`: your local time (tests pass it); default the clock in your timezone."""
    now = now or local_now(user)
    today = now.date()
    settings = load_settings(session, user.id)
    recipe, version = _version(session, user.id, body.version_id)
    ensure_steps(session, user, version, access)
    search = get_search(session, user.id, body.search_id) if body.search_id is not None else None
    resolved: dict[str, Any] = (search.results or {}).get("resolved", {}) if search is not None else {}
    answers = CookAnswers.model_validate(search.answers) if search is not None else None
    if search is not None and (existing := _existing(session, search, version.id)) is not None:
        return _out(session, user.id, existing.meal_plan_id, existing.id, created=False)
    asked = body.slot or (MealSlot(resolved["slot"]) if resolved.get("slot") else None)
    slot = choose_slot(asked, list(version.meal_slots), slot_from_clock(now))
    portions = body.portions or int(resolved.get("people") or settings.household_size)
    diet = diet_inputs(session, user.id, settings)
    stores, _ = store_ids(session, settings)
    ingredient_ids = set(
        session.scalars(
            select(RecipeIngredient.ingredient_id).where(RecipeIngredient.recipe_version_id == version.id)
        )
    )
    used = meals_this_week(session, user.id, diet.caps, today)
    for label, members in used_up(diet.caps, used).items():
        if ingredient_ids & members:
            raise CookThisError(f"{label}: this week's allowance is already used")
    off = {t.ingredient_id for t in answers.pantry if not t.include} if answers else set()
    have = {e.ingredient_id for e in answers.extras if e.status == "have"} if answers else set()
    off_lots = frozenset(
        session.scalars(
            select(InventoryItem.id).where(
                InventoryItem.user_id == user.id,
                InventoryItem.ingredient_id.in_(off - have),
                InventoryItem.status == "active",
            )
        )
    )
    c = constraints_for_meal(
        settings,
        diet,
        stores,
        off_lot_ids=off_lots,
        today=today,
        slot=slot,
        portions=portions,
        mood=RecipeMood(resolved["mood"]) if resolved.get("mood") else RecipeMood.FANCY,
        minutes=int(resolved.get("quick_minutes") or NO_TIME_LIMIT),
        answers=answers,
    )
    if resolved.get("portion_size"):
        c = c.model_copy(update={"default_portion_size": PortionSize(resolved["portion_size"])})
    plan = build_meal_plan(session, user.id, c, recipe, version)
    report = validate_plan(plan, load_reference(session, user.id, c, [version.id]), scope="single")
    if not report.ok:
        raise CookThisError(
            "This meal didn't pass the checks: " + "; ".join(e.message for e in report.errors)
        )
    run_id = search.generation_run_id if search is not None else None
    saved = save_plan(session, user.id, plan, report, run_id, kind=SINGLE)
    batch_id = session.scalars(select(PlanCookBatch.id).where(PlanCookBatch.meal_plan_id == saved.id)).one()
    if search is not None:
        search.meal_plan_id = saved.id
        # the meal-now exposure: you cooked this one (F9); More ideas logs what it shows under its tap's run
        runs = [int(i) for i in (search.results or {}).get("run_ids", [])] or ([run_id] if run_id else [])
        if runs:
            session.execute(
                update(PlanCandidate)
                .where(
                    PlanCandidate.generation_run_id.in_(runs),
                    PlanCandidate.recipe_version_id == version.id,
                    PlanCandidate.filtered_reason.is_(None),
                )
                .values(selected=True, portions_selected=portions, meal_plan_id=saved.id)
            )
    session.flush()
    return _out(session, user.id, saved.id, batch_id, created=True)
