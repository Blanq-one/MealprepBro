"""Planning runs and plan read models: start a run, run it to completion inside the request (Phase 2: nothing
continues after the response, as on a serverless host), and show the plan summary (PRD §25) and the
store-grouped grocery list. Display strings only; every number comes from code."""

import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import (
    CookSearch,
    GenerationRun,
    GroceryList,
    GroceryListItem,
    MealPlan,
    PlanBatchIngredient,
    PlanCookBatch,
    PlanMeal,
    Product,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
    Store,
)
from app.domain.cook_schedule import DaySchedule, DishTiming, minutes_text, timeline
from app.domain.cost import money_display
from app.domain.enums import MealSlot
from app.domain.units import GRAMS_PER_UNIT, ML_PER_UNIT
from app.llm.client import LLMClient
from app.llm.errors import LLMConfigError
from app.planning.orchestrator import Orchestrator, PlanOutcome, ProgressListener, problem_json
from app.planning.perishables import freeze_text
from app.planning.persistence import SINGLE, PlanNotFoundError, accept_plan
from app.planning.problem import IngredientPlan
from app.planning.recipe_math import nutrition_of
from app.planning.rounded import FreezeInstruction, meal_key
from app.planning.solver.model import proven_best
from app.planning.timing import day_schedules, dish_batch, load_timings
from app.schemas.plans import (
    BatchOut,
    CostsOut,
    DayOut,
    FreezeOut,
    GenerationRunOut,
    GroceryGroupOut,
    GroceryItemOut,
    GroceryListOut,
    LeftoverOut,
    MealOut,
    PlanListItemOut,
    PlanRequest,
    PlanSummaryOut,
    PrepNoteOut,
    PrepNotesOut,
    StoreTotalOut,
    TimelineLineOut,
)
from app.services import plan_view as view
from app.services.dishes import dish_categories
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.settings import ALWAYS_HAVE_SLUGS

log = logging.getLogger(__name__)

ClientFactory = Callable[[], LLMClient | None]


class RunNotFoundError(LookupError):
    pass


def money(cents: int) -> str:
    return money_display(cents)


def cash_split_display(regular_cents: int, stock_up_cents: int) -> str:
    """'$52.91 groceries + $90.43 stock-up': groceries and stock-up are always shown apart."""
    text = f"{money(regular_cents)} groceries"
    return f"{text} + {money(stock_up_cents)} stock-up" if stock_up_cents else text


NOTHING_TO_COOK = "Nothing to cook, eating prepped meals"


def cook_note(cooked: list[tuple[str, int]]) -> str:
    """The day note: what to cook that day (title, portions), or that the day eats prepped meals."""
    if not cooked:
        return NOTHING_TO_COOK
    return "Cook: " + ", ".join(f"{title} ({n} portion{'s' if n != 1 else ''})" for title, n in cooked)


def shows_as_zero(quantity: Decimal, unit: str) -> bool:
    """Whether amount_display would print 0 (a pinch of a spice)."""
    step = Decimal("0.5") if unit == "count" else Decimal(1)
    return (quantity / step).quantize(Decimal(1), ROUND_HALF_UP) == 0


def amount_display(quantity: Decimal, unit: str) -> str:
    """'1,580 g (3.48 lb)', '884 ml (3.7 cups)', '15'."""
    if unit == "count":
        q = (
            quantity.quantize(Decimal("0.5"), ROUND_HALF_UP)
            if quantity % 1
            else quantity.quantize(Decimal(1))
        )
        return f"{q.normalize():f}"
    if unit == "g":
        text = f"{quantity.quantize(Decimal(1), ROUND_HALF_UP):,} g"
        if quantity >= 227:
            text += f" ({(quantity / GRAMS_PER_UNIT['lb']).quantize(Decimal('0.01'), ROUND_HALF_UP)} lb)"
        return text
    text = f"{quantity.quantize(Decimal(1), ROUND_HALF_UP):,} ml"
    if quantity >= 240:
        text += f" ({(quantity / ML_PER_UNIT['cup']).quantize(Decimal('0.1'), ROUND_HALF_UP)} cups)"
    return text


# ---------------- runs ----------------
UNFINISHED = ("pending", "running")
NO_LLM_NOTE = "Recipe generation isn't set up ({reason}), so this plan uses saved and seed recipes only."


def expire_stale_runs(session: Session, user_id: int, older_than_s: int) -> int:
    """A run still pending or running long after any request could have ended was cut off (the function was
    stopped, or the app was closed mid-plan): mark it failed so it never looks like it's still working."""
    cutoff = datetime.now(UTC) - timedelta(seconds=older_than_s)
    stale = list(
        session.scalars(
            select(GenerationRun).where(
                GenerationRun.user_id == user_id,
                GenerationRun.status.in_(UNFINISHED),
                GenerationRun.created_at < cutoff,
            )
        )
    )
    for run in stale:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error = problem_json(
            "Planning was interrupted",
            "This run stopped before it finished (the request ended early); nothing from it was saved.",
            status=500,
            code="interrupted",
        )
    session.flush()
    return len(stale)


def start_run(
    session: Session, user_id: int, request: PlanRequest, purpose: str = "weekly_plan"
) -> GenerationRun:
    expire_stale_runs(session, user_id, get_settings().plan_stale_after_seconds)
    run = GenerationRun(
        user_id=user_id,
        purpose=purpose,
        status="pending",
        progress={"stage": "queued", "request": request.model_dump(mode="json")},
    )
    session.add(run)
    session.flush()
    return run


def execute_run(
    session: Session,
    run: GenerationRun,
    request: PlanRequest,
    client_factory: ClientFactory,
    *,
    on_progress: ProgressListener | None = None,
    kind: str | None = None,
    ideas: bool = False,
    today: date | None = None,
) -> PlanOutcome:
    """Run the orchestrator to the end, in this request and this session. Commits what happened (the run
    record, its LLM calls, saved recipes and the plan); an unexpected crash rolls back and marks the run
    failed, so a run never stays "running". `kind` and `ideas`: a meal-prep plan (step 2b.5) is saved with its
    kind and fills gaps with the ideas pass."""
    notes: list[str] = []
    client: LLMClient | None = None
    if request.allow_llm:
        try:
            client = client_factory()
        except LLMConfigError as exc:
            notes.append(NO_LLM_NOTE.format(reason=exc))
    run_id, user_id = run.id, run.user_id
    try:
        outcome = Orchestrator(
            session, user_id, llm_client=client, on_progress=on_progress, kind=kind, ideas=ideas, today=today
        ).run(request, run)
        outcome.notes = [*notes, *outcome.notes]
        session.commit()
        return outcome
    except Exception as exc:
        log.exception("planning run %s crashed", run_id)
        session.rollback()
        error = problem_json("Planning crashed", str(exc), status=500, code="internal")
        failed = session.get(GenerationRun, run_id)
        if failed is not None:
            failed.status = "failed"
            failed.finished_at = datetime.now(UTC)
            failed.error = error
            session.commit()
        return PlanOutcome("failed", run_id, error=error, notes=notes)


def run_plan_now(
    session: Session, user_id: int, request: PlanRequest, client: LLMClient | None
) -> PlanOutcome:
    """Synchronous run (CLI): same orchestrator, same lifecycle."""
    return Orchestrator(session, user_id, llm_client=client).run(request)


def run_view(session: Session, user_id: int, run_id: int) -> GenerationRunOut:
    run = session.get(GenerationRun, run_id)
    if run is None or run.user_id != user_id:
        raise RunNotFoundError(f"generation run {run_id} not found")
    plan_id = session.scalars(select(MealPlan.id).where(MealPlan.generation_run_id == run.id)).first()
    return GenerationRunOut(
        id=run.id,
        purpose=run.purpose,
        status=run.status,
        progress=run.progress,
        error=run.error,
        plan_id=plan_id,
        llm_call_count=run.llm_call_count,
        total_tokens=run.total_tokens,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


# ---------------- plan summary ----------------
def _plan(session: Session, user_id: int, plan_id: int) -> MealPlan:
    plan = session.get(MealPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise PlanNotFoundError(f"plan {plan_id} not found")
    return plan


def batch_nutrition(session: Session, batch_ids: list[int]) -> dict[int, dict[str, Decimal]]:
    """Per-portion nutrition of each stored batch, recomputed from its practical quantities."""
    rows = list(
        session.scalars(select(PlanBatchIngredient).where(PlanBatchIngredient.cook_batch_id.in_(batch_ids)))
    )
    batches = {b.id: b for b in session.scalars(select(PlanCookBatch).where(PlanCookBatch.id.in_(batch_ids)))}
    data = load_ingredients(session, {r.ingredient_id for r in rows})
    plans = {i: IngredientPlan(i, d.name, "g", d.units, d.profile) for i, d in data.items()}
    optional = _optional_lines(session, rows)
    by_batch: dict[int, list[tuple[int, Decimal, str]]] = defaultdict(list)
    for r in rows:
        if r.recipe_ingredient_id not in optional:
            by_batch[r.cook_batch_id].append((r.ingredient_id, r.quantity, r.unit))
    out = {}
    for batch_id, amounts in by_batch.items():
        totals = nutrition_of(amounts, plans)
        out[batch_id] = {k: v / Decimal(batches[batch_id].portions) for k, v in totals.amounts.items()}
    return out


def _optional_lines(session: Session, rows: list[PlanBatchIngredient]) -> set[int]:
    ids = {r.recipe_ingredient_id for r in rows if r.recipe_ingredient_id is not None}
    if not ids:
        return set()
    return set(
        session.scalars(
            select(RecipeIngredient.id).where(
                RecipeIngredient.id.in_(ids), RecipeIngredient.is_optional.is_(True)
            )
        )
    )


def plan_summary(session: Session, user_id: int, plan_id: int) -> PlanSummaryOut:
    plan = _plan(session, user_id, plan_id)
    c: dict[str, Any] = plan.constraints
    totals: dict[str, Any] = plan.totals
    batches = list(
        session.scalars(
            select(PlanCookBatch)
            .where(PlanCookBatch.meal_plan_id == plan.id)
            .order_by(PlanCookBatch.cook_on, PlanCookBatch.id)
        )
    )
    versions = {
        v.id: (v, r)
        for v, r in session.execute(
            select(RecipeVersion, Recipe)
            .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
            .where(RecipeVersion.id.in_([b.recipe_version_id for b in batches]))
        ).tuples()
    }
    nutrition = batch_nutrition(session, [b.id for b in batches])
    batch_by_id = {b.id: b for b in batches}
    categories = dish_categories(session, [b.recipe_version_id for b in batches])
    costs = totals["costs"]
    meal_cents: dict[str, int] = costs.get("meal_cents", {})
    day_cents: dict[str, int] = costs.get("day_cents", {})
    # stored in plan order, and batches are written in plan order (ascending ids)
    stored_batch_cents: list[int] = costs.get("batch_cents", [])
    in_plan_order = sorted(batches, key=lambda b: b.id)
    batch_cents = (
        {b.id: cents for b, cents in zip(in_plan_order, stored_batch_cents, strict=True)}
        if len(stored_batch_cents) == len(in_plan_order)
        else {}
    )
    meals = list(
        session.scalars(
            select(PlanMeal).where(PlanMeal.meal_plan_id == plan.id, PlanMeal.status != "replaced")
        )
    )
    slot_order = {s.value: i for i, s in enumerate(MealSlot)}
    meals.sort(key=lambda m: (m.eat_on, slot_order.get(m.slot, 99)))
    household = int(c.get("household_size", 1))
    split = {
        b.id: view.portion_split(
            b.portions,
            sum(1 for m in meals if m.cook_batch_id == b.id and m.from_freezer),
            household,
            b.portions_to_freeze,
        )
        for b in batches
    }
    freeze = _freeze_instructions(totals)
    schedules, lines = _cook_days(batches, versions, load_timings(session, [v for v, _ in versions.values()]))
    days_out = []
    for spec in c["days"]:
        day = date.fromisoformat(spec["day"])
        meals_out = []
        thaw = [
            view.thaw_note(
                MealSlot(m.slot), versions[batch_by_id[m.cook_batch_id].recipe_version_id][0].title
            )
            for m in meals
            if m.from_freezer and m.cook_batch_id is not None and m.eat_on == day + timedelta(days=1)
        ]
        for m in meals:
            if m.eat_on != day or m.cook_batch_id is None:
                continue
            b = batch_by_id[m.cook_batch_id]
            v, r = versions[b.recipe_version_id]
            storage, source = view.meal_source(m.eat_on, b.cook_on, m.from_freezer)
            protein = (
                nutrition.get(b.id, {}).get("protein_g", Decimal(0)).quantize(Decimal("0.1"), ROUND_HALF_UP)
            )
            cents = meal_cents.get(meal_key(m.eat_on, m.slot))
            meals_out.append(
                MealOut(
                    eat_on=m.eat_on,
                    slot=MealSlot(m.slot),
                    recipe_version_id=v.id,
                    recipe_id=r.id,
                    title=v.title,
                    is_draft=v.is_draft,
                    kcal=m.planned_kcal,
                    protein_g=protein,
                    from_freezer=m.from_freezer,
                    cook_batch_id=b.id,
                    note="From the freezer: move it to the fridge the night before."
                    if m.from_freezer
                    else None,
                    dish_category=categories[v.id].value,
                    cost_cents=cents,
                    cost_display=money(cents) if cents is not None else None,
                    storage=storage,
                    source_display=source,
                )
            )
        today_batches = [b for b in batches if b.cook_on == day]
        cooked = [(versions[b.recipe_version_id][0].title, b.portions) for b in today_batches]
        cents_today = day_cents.get(day.isoformat())
        days_out.append(
            DayOut(
                day=day,
                is_cook_day=spec["is_cook_day"],
                kcal=totals["day_kcal"].get(day.isoformat(), 0),
                kcal_target=spec["kcal_target"],
                protein_g=Decimal(totals["day_protein_g"].get(day.isoformat(), "0")),
                hands_on_minutes=schedules[day].hands_on if day in schedules else 0,
                elapsed_minutes=schedules[day].elapsed if day in schedules else 0,
                chill_minutes=schedules[day].fridge_minutes if day in schedules else 0,
                cook_minutes_available=spec["cook_minutes_available"],
                meals=meals_out,
                cook_note=cook_note(cooked),
                cost_cents=cents_today,
                cost_display=money(cents_today) if cents_today is not None else None,
                freeze_steps=[
                    freeze_text(f, amount_display(f.quantity, f.unit)) for f in freeze if f.freeze_on == day
                ],
                freeze_today=[
                    view.freeze_today(versions[b.recipe_version_id][0].title, split[b.id][1])
                    for b in today_batches
                    if split[b.id][1]
                ],
                thaw_notes=thaw,
                timeline=lines.get(day, []),
                time_display=_time_display(schedules[day]) if day in schedules else None,
            )
        )
    stores = {s.id: s.name for s in session.scalars(select(Store))}
    store_totals = [
        StoreTotalOut(
            store_id=int(sid), store_name=stores.get(int(sid), "?"), cents=cents, display=money(cents)
        )
        for sid, cents in totals["store_cents"].items()
    ]
    week_protein = Decimal(totals["week_protein_g"])
    n_days = len(c["days"])
    report = plan.validation_report
    unpriced = totals["unpriced"]
    notes_items = [
        PrepNoteOut(kind="freeze", text=freeze_text(f, amount_display(f.quantity, f.unit)), day=f.freeze_on)
        for f in freeze
    ]
    notes_items += [
        PrepNoteOut(
            kind="freeze_portions",
            text=view.freeze_portions_note(
                versions[b.recipe_version_id][0].title,
                split[b.id][1],
                b.cook_on,
                versions[b.recipe_version_id][0].freeze_note,
            ),
            day=b.cook_on,
        )
        for b in batches
        if split[b.id][1]
    ]
    spoil = [
        PrepNoteOut(
            kind="spoil",
            text=view.spoil_note(item["name"], amount_display(Decimal(item["quantity"]), item["unit"])),
        )
        for item in totals["leftovers"]
        if item["fate"] == "at_risk"
    ]
    to_freeze = len(notes_items)
    notes_items += spoil
    display = view.prep_notes_display(to_freeze, len(spoil))
    search = session.scalars(select(CookSearch).where(CookSearch.meal_plan_id == plan.id)).first()
    return PlanSummaryOut(
        id=plan.id,
        week_start=plan.week_start,
        status=plan.status,
        kind=plan.kind,
        calorie_mode=c["calorie_mode"],
        kcal_target_week=c["weekly_kcal_target"],
        kcal_planned_week=totals["week_kcal"],
        nutrition_focus=c["nutrition_priority"],
        secondary_focus=c["secondary_priority"],
        planning_mode=c["planning_mode"],
        purchase_limit_cents=c["purchase_limit_cents"],
        protein_target_g_per_day=c["daily_protein_target_g"],
        estimated_cost_cents=totals["cost_cents"],
        estimated_cost_display=money(totals["cost_cents"])
        + ("" if totals["cost_complete"] else " + unpriced items"),
        cost_complete=totals["cost_complete"],
        cost_note=f"Incomplete: no price yet for {', '.join(unpriced)}" if unpriced else None,
        store_totals=store_totals,
        cooking_minutes_total=sum(s.hands_on for s in schedules.values()),
        meals_count=totals["meals"],
        protein_g_week=week_protein,
        protein_g_per_day=(week_protein / n_days).quantize(Decimal("0.1"), ROUND_HALF_UP),
        costs=CostsOut(
            cash_cents=costs["cash_cents"],
            cash_display=money(costs["cash_cents"]),
            regular_cash_cents=costs["regular_cash_cents"],
            stock_up_cash_cents=costs["stock_up_cash_cents"],
            eaten_cents=costs["eaten_cents"],
            eaten_display=money(costs["eaten_cents"]),
            from_inventory_cents=costs["from_inventory_cents"],
            leftover_cents=costs["leftover_cents"],
            leftover_display=money(costs["leftover_cents"]),
            frozen_portions_cents=costs["frozen_portions_cents"],
            expected_waste_cents=costs["expected_waste_cents"],
            expected_waste_display=money(costs["expected_waste_cents"]),
            complete=costs["complete"],
            unpriced=list(costs["unpriced"]),
            cash_split_display=cash_split_display(costs["regular_cash_cents"], costs["stock_up_cash_cents"]),
        ),
        leftovers=[
            LeftoverOut(
                ingredient_id=item["ingredient_id"],
                name=item["name"],
                amount=amount_display(Decimal(item["quantity"]), item["unit"]),
                cents=item["cents"],
                fate=item["fate"],
            )
            for item in totals["leftovers"]
        ],
        freeze=[
            FreezeOut(
                ingredient_id=f.ingredient_id,
                name=f.name,
                amount=amount_display(f.quantity, f.unit),
                freeze_on=f.freeze_on,
                use_on=f.use_on,
                thaw_on=f.thaw_on,
                recipe=f.recipe,
                source=f.source,
                message=freeze_text(f, amount_display(f.quantity, f.unit)),
            )
            for f in freeze
        ],
        days=days_out,
        batches=[
            BatchOut(
                id=b.id,
                recipe_version_id=b.recipe_version_id,
                title=versions[b.recipe_version_id][0].title,
                cook_on=b.cook_on,
                portions=b.portions,
                portions_to_freeze=b.portions_to_freeze,
                portion_size=b.portion_size,
                portion_multiplier=b.portion_multiplier,
                scale_factor=b.scale_factor,
                planned_minutes=b.planned_minutes,
                status=b.status,
                dish_category=categories[b.recipe_version_id].value,
                cost_cents=batch_cents.get(b.id),
                cost_display=money(batch_cents[b.id]) if b.id in batch_cents else None,
                fridge_portions=split[b.id][0],
                freezer_portions=split[b.id][1],
                portions_display=view.portions_display(b.portions, *split[b.id]),
                freezer_friendly=versions[b.recipe_version_id][0].freezer_friendly,
                freeze_note=versions[b.recipe_version_id][0].freeze_note,
            )
            for b in batches
        ],
        warnings=list(report.get("warnings", [])),
        notes=list(report.get("notes", [])),
        generation_run_id=plan.generation_run_id,
        prep_notes=PrepNotesOut(display=display, items=notes_items) if display else None,
        header=(search.results or {}).get("header") if search is not None else None,
        household_size=household,
        proven_best=proven_best(plan.solver_status),
    )


def _freeze_instructions(totals: dict[str, Any]) -> list[FreezeInstruction]:
    return [
        FreezeInstruction(
            ingredient_id=f["ingredient_id"],
            name=f["name"],
            unit=f["unit"],
            quantity=Decimal(f["quantity"]),
            freeze_on=date.fromisoformat(f["freeze_on"]),
            fridge_days=f["fridge_days"],
            source=f["source"],
            use_on=date.fromisoformat(f["use_on"]) if f["use_on"] else None,
            recipe=f["recipe"],
        )
        for f in totals["freeze"]
    ]


def _cook_days(
    batches: list[PlanCookBatch],
    versions: dict[int, tuple[RecipeVersion, Recipe]],
    timings: dict[int, DishTiming],
) -> tuple[dict[date, DaySchedule], dict[date, list[TimelineLineOut]]]:
    """Each cook day's schedule and timeline (step 2b.9), from the plan's batches and their recipes' tasks."""
    pairs = []
    batch_ids: dict[tuple[date, str], int] = {}
    for b in batches:
        version = versions[b.recipe_version_id][0]
        batch = dish_batch(
            b.recipe_version_id,
            b.portion_size,
            title=version.title,
            timing=timings[b.recipe_version_id],
            base_servings=version.base_servings,
            portions=b.portions,
        )
        pairs.append((b.cook_on, batch))
        batch_ids[(b.cook_on, batch.key)] = b.id
    schedules = day_schedules(pairs)
    lines: dict[date, list[TimelineLineOut]] = {}
    for day, schedule in schedules.items():
        out = []
        for line in timeline(schedule):
            dish = schedule.dishes[line.dish] if line.dish is not None else None
            out.append(
                TimelineLineOut(
                    at_min=line.at_min,
                    at_display=line.at_display,
                    text=line.text,
                    kind=line.kind,
                    minutes=line.minutes,
                    equipment=line.equipment,
                    estimated=line.estimated,
                    dish=dish.title if dish is not None else None,
                    cook_batch_id=batch_ids[(day, dish.key)] if dish is not None else None,
                )
            )
        lines[day] = out
    return schedules, lines


def _time_display(schedule: DaySchedule) -> str:
    """'about 1 h start to finish · 35 min hands-on'."""
    return (
        f"about {minutes_text(schedule.elapsed)} start to finish · {minutes_text(schedule.hands_on)} hands-on"
    )


def accept(
    session: Session, user_id: int, plan_id: int, *, replace_overlapping: bool = False
) -> PlanSummaryOut:
    accept_plan(session, user_id, plan_id, replace_overlapping=replace_overlapping)
    return plan_summary(session, user_id, plan_id)


def current_plan_id(plans: list[MealPlan], today: date) -> int | None:
    """The plan the app opens on: the active plan for this week, else the latest active plan, else the
    latest draft (plans newest first). A one-meal plan (Cook this) is never the current plan."""

    def covers(p: MealPlan) -> bool:
        days = len(p.constraints.get("days", [])) or 7
        return p.week_start <= today < p.week_start + timedelta(days=days)

    plans = [p for p in plans if p.kind != SINGLE]
    active = [p for p in plans if p.status == "active"]
    for group in ([p for p in active if covers(p)], active, [p for p in plans if p.status == "draft"]):
        if group:
            return group[0].id
    return None


def list_plans(
    session: Session, user_id: int, limit: int, today: date | None = None
) -> list[PlanListItemOut]:
    plans = list(
        session.scalars(
            select(MealPlan)
            .where(
                MealPlan.user_id == user_id,
                MealPlan.status.in_(("active", "draft", "completed")),
                or_(MealPlan.kind.is_(None), MealPlan.kind != SINGLE),  # one-meal plans aren't listed
            )
            .order_by(MealPlan.created_at.desc(), MealPlan.id.desc())
            .limit(limit)
        )
    )
    current = current_plan_id(plans, today or datetime.now(UTC).date())
    return [
        PlanListItemOut(
            id=p.id,
            week_start=p.week_start,
            status=p.status,
            created_at=p.created_at,
            planning_mode=p.constraints["planning_mode"],
            kcal_planned_week=p.totals["week_kcal"],
            kcal_target_week=p.constraints["weekly_kcal_target"],
            meals_count=p.totals["meals"],
            cash_display=money(p.totals["costs"]["cash_cents"]),
            is_current=p.id == current,
            kind=p.kind,
        )
        for p in plans
    ]


# ---------------- grocery list ----------------
def grocery_item_out(
    it: GroceryListItem,
    data: dict[int, IngredientData],
    stores: dict[int, str],
    products: dict[int, str],
) -> GroceryItemOut:
    reason = it.reason or {}
    kind = reason.get("kind", "buy")
    to_buy_total = Decimal(reason.get("to_buy_total", it.to_buy_quantity))
    ingredient = data.get(it.ingredient_id)
    # a pinch of a staple would read "0 g": "check you have" shows the name only
    pinch = kind == "staple" and shows_as_zero(it.needed_quantity, it.unit)
    return GroceryItemOut(
        id=it.id,
        ingredient_id=it.ingredient_id,
        name=ingredient.name if ingredient else "?",
        category=ingredient.category if ingredient else "other",
        store_id=it.store_id,
        store_name=stores.get(it.store_id) if it.store_id else None,
        product_id=it.product_id,
        product_name=products.get(it.product_id) if it.product_id else None,
        needed="" if pinch else amount_display(it.needed_quantity, it.unit),
        from_inventory=amount_display(it.inventory_used_quantity, it.unit)
        if it.inventory_used_quantity
        else None,
        to_buy=(
            f"{it.packages} × {products.get(it.product_id or 0, 'package')}"
            if it.packages
            else ""
            if pinch
            else amount_display(to_buy_total if kind != "buy" else it.to_buy_quantity, it.unit)
        ),
        packages=it.packages,
        estimated_cost_cents=it.estimated_cost_cents,
        estimated_cost_display=(
            money(it.estimated_cost_cents) + (" est." if reason.get("is_estimate") else "")
        )
        if it.estimated_cost_cents is not None
        else None,
        is_estimate=bool(reason.get("is_estimate")),
        expected_remainder=amount_display(it.expected_remainder_quantity, it.unit) + " left (open package)"
        if it.expected_remainder_quantity
        else None,
        kind=kind,
        note=reason.get("note"),
        stock_up=bool(reason.get("stock_up")),
        checked=it.checked_at is not None,
        checked_at=it.checked_at,
        purchased=amount_display(it.purchased_quantity, it.unit)
        if it.purchased_quantity is not None
        else None,
        actual_price_cents=it.actual_price_cents,
        actual_price_display=money(it.actual_price_cents) if it.actual_price_cents is not None else None,
    )


CATEGORY_ORDER = (
    "protein",
    "dairy",
    "vegetable",
    "fruit",
    "grain",
    "legume",
    "nut_seed",
    "fat_oil",
    "condiment",
    "sweetener",
    "spice",
    "supplement",
    "beverage",
    "other",
)
SECTION_TITLES = {
    "stock_up": "Also buy this week (stock-up)",
    "inventory": "From your inventory",
    "staple": "Check you have",
    "unpriced": "No price yet",
}


def _section(item: GroceryItemOut) -> str | None:
    """Items outside the per-store (or per-category) groups get their own section."""
    if item.kind == "buy" and item.stock_up:
        return "stock_up"
    if item.kind == "from_inventory":
        return "inventory"
    if item.kind == "staple":
        return "staple"
    if item.kind == "unpriced" or (item.kind == "buy" and item.store_id is None):
        return "unpriced"
    return None


def _groups(
    items: list[GroceryItemOut], group_by: str, store_order: list[int], stores: dict[int, str]
) -> list[GroceryGroupOut]:
    def group(
        kind: str, title: str, members: list[GroceryItemOut], store_id: int | None = None
    ) -> GroceryGroupOut:
        cents = sum(i.estimated_cost_cents or 0 for i in members)
        return GroceryGroupOut(
            kind=kind,
            key=f"{kind}:{store_id if store_id is not None else title}",
            store_id=store_id,
            store_name=title,
            subtotal_cents=cents,
            subtotal_display=money(cents),
            items=members,
        )

    if group_by == "none":
        return [group("all", "All items", items)]
    sections: dict[str, list[GroceryItemOut]] = defaultdict(list)
    regular: list[GroceryItemOut] = []
    for item in items:
        if (section := _section(item)) is not None:
            sections[section].append(item)
        else:
            regular.append(item)
    out: list[GroceryGroupOut] = []
    if group_by == "category":
        by_category: dict[str, list[GroceryItemOut]] = defaultdict(list)
        for item in regular:
            by_category[item.category].append(item)
        rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
        for category in sorted(by_category, key=lambda c: (rank.get(c, len(rank)), c)):
            out.append(group("category", category.replace("_", " ").capitalize(), by_category[category]))
    else:
        by_store: dict[int, list[GroceryItemOut]] = defaultdict(list)
        for item in regular:
            by_store[item.store_id or 0].append(item)
        store_rank = {sid: i for i, sid in enumerate(store_order)}
        for sid in sorted(by_store, key=lambda s: (store_rank.get(s, len(store_rank)), s)):
            out.append(group("store", stores.get(sid, "?"), by_store[sid], sid))
    for section in ("stock_up", "inventory", "staple", "unpriced"):
        if sections[section]:
            out.append(group(section, SECTION_TITLES[section], sections[section]))
    return out


def grocery_view(session: Session, user_id: int, plan_id: int, group_by: str = "store") -> GroceryListOut:
    plan = _plan(session, user_id, plan_id)
    glist = session.scalars(select(GroceryList).where(GroceryList.meal_plan_id == plan.id)).first()
    if glist is None:
        raise PlanNotFoundError(f"plan {plan_id} has no grocery list")
    items = list(
        session.scalars(
            select(GroceryListItem)
            .where(GroceryListItem.grocery_list_id == glist.id)
            .order_by(GroceryListItem.position)
        )
    )
    data = load_ingredients(session, {it.ingredient_id for it in items})
    # never list water or Always-have items (plans saved before Phase 2b listed them as staples)
    always_have = set(plan.constraints.get("always_have_ingredient_ids", ()))
    items = [
        it
        for it in items
        if it.ingredient_id not in always_have
        and not (it.ingredient_id in data and data[it.ingredient_id].slug in ALWAYS_HAVE_SLUGS)
    ]
    stores = {s.id: s.name for s in session.scalars(select(Store))}
    products = {
        p.id: p.name
        for p in session.scalars(
            select(Product).where(Product.id.in_({it.product_id for it in items if it.product_id}))
        )
    }
    out_items = [grocery_item_out(it, data, stores, products) for it in items]
    primary_id = plan.constraints["store_ids"][0]
    group_out = _groups(out_items, group_by, list(plan.constraints["store_ids"]), stores)
    totals = plan.totals
    threshold = plan.constraints["store_split_min_savings_cents"]
    split_info = totals.get("grocery", {})
    savings = int(split_info.get("savings_cents") or 0)
    stock_up_cents = int(split_info.get("stock_up_cents") or 0)
    split = bool(split_info.get("split"))  # the store choice (R4), not items only priced elsewhere
    note = None
    if split:
        others = sorted(
            {
                stores[i.store_id]
                for i in out_items
                if i.store_id is not None
                and i.store_id != primary_id
                and i.note != "only priced at another store"
            }
        )
        note = (
            f"Buying at {', '.join(others)} saves {money(savings)} this week compared with "
            f"{stores.get(primary_id, 'your primary store')} alone "
            f"(you split only for {money(threshold)} or more)."
        )
    elif savings > 0:
        note = (
            f"Everything at {stores.get(primary_id, 'your primary store')}: another store would save only "
            f"{money(savings)} (under {money(threshold)})."
        )
    return GroceryListOut(
        id=glist.id,
        plan_id=plan.id,
        status=glist.status,
        group_by=group_by,
        checked_count=sum(1 for i in out_items if i.checked),
        to_check_count=sum(1 for i in out_items if i.kind == "buy"),
        total_cents=totals["cost_cents"],
        total_display=money(totals["cost_cents"]),
        regular_cents=totals["cost_cents"] - stock_up_cents,
        stock_up_cents=stock_up_cents,
        cash_split_display=cash_split_display(totals["cost_cents"] - stock_up_cents, stock_up_cents),
        complete=totals["cost_complete"],
        unpriced=list(totals["unpriced"]),
        split=split,
        savings_cents=savings,
        split_threshold_cents=threshold,
        note=note,
        groups=group_out,
    )
