"""Planning runs and plan read models: start a run (202 + run id), execute it in the background, and show the
plan summary (PRD §25) and the store-grouped grocery list. Display strings only; every number comes from
code."""

import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
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
from app.domain.enums import MealSlot
from app.domain.units import GRAMS_PER_UNIT, ML_PER_UNIT
from app.llm.client import LLMClient
from app.planning.orchestrator import Orchestrator, PlanOutcome, problem_json
from app.planning.persistence import PlanNotFoundError, accept_plan
from app.planning.problem import IngredientPlan
from app.planning.recipe_math import nutrition_of
from app.schemas.plans import (
    BatchOut,
    DayOut,
    GenerationRunOut,
    GroceryGroupOut,
    GroceryItemOut,
    GroceryListOut,
    MealOut,
    PlanRequest,
    PlanSummaryOut,
    StoreTotalOut,
)
from app.services.ingredient_data import load_ingredients

log = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]
ClientFactory = Callable[[], LLMClient | None]


class RunNotFoundError(LookupError):
    pass


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


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
def start_run(session: Session, user_id: int, request: PlanRequest) -> GenerationRun:
    run = GenerationRun(
        user_id=user_id,
        purpose="weekly_plan",
        status="pending",
        progress={"stage": "queued", "request": request.model_dump(mode="json")},
    )
    session.add(run)
    session.flush()
    return run


def execute_run(
    session_factory: SessionFactory, run_id: int, request: PlanRequest, client_factory: ClientFactory
) -> None:
    """Background task: run the orchestrator in its own session and commit whatever happened."""
    session = session_factory()
    try:
        run = session.get(GenerationRun, run_id)
        if run is None:
            return
        client = client_factory() if request.allow_llm else None
        Orchestrator(session, run.user_id, llm_client=client).run(request, run)
        session.commit()
    except Exception as exc:  # pragma: no cover - last-resort guard so a run never stays "running"
        log.exception("planning run %s crashed", run_id)
        session.rollback()
        run = session.get(GenerationRun, run_id)
        if run is not None:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error = problem_json("Planning crashed", str(exc), status=500, code="internal")
            session.commit()
    finally:
        session.close()


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
    meals = list(
        session.scalars(
            select(PlanMeal).where(PlanMeal.meal_plan_id == plan.id, PlanMeal.status != "replaced")
        )
    )
    slot_order = {s.value: i for i, s in enumerate(MealSlot)}
    meals.sort(key=lambda m: (m.eat_on, slot_order.get(m.slot, 99)))
    days_out = []
    for spec in c["days"]:
        day = date.fromisoformat(spec["day"])
        meals_out = []
        for m in meals:
            if m.eat_on != day or m.cook_batch_id is None:
                continue
            b = batch_by_id[m.cook_batch_id]
            v, r = versions[b.recipe_version_id]
            protein = (
                nutrition.get(b.id, {}).get("protein_g", Decimal(0)).quantize(Decimal("0.1"), ROUND_HALF_UP)
            )
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
                )
            )
        days_out.append(
            DayOut(
                day=day,
                is_cook_day=spec["is_cook_day"],
                kcal=totals["day_kcal"].get(day.isoformat(), 0),
                kcal_target=spec["kcal_target"],
                protein_g=Decimal(totals["day_protein_g"].get(day.isoformat(), "0")),
                hands_on_minutes=totals["hands_on_minutes"].get(day.isoformat(), 0),
                cook_minutes_available=spec["cook_minutes_available"],
                meals=meals_out,
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
    return PlanSummaryOut(
        id=plan.id,
        week_start=plan.week_start,
        status=plan.status,
        calorie_mode=c["calorie_mode"],
        kcal_target_week=c["weekly_kcal_target"],
        kcal_planned_week=totals["week_kcal"],
        nutrition_focus=c["nutrition_priority"],
        secondary_focus=c["secondary_priority"],
        budget_cents=c["weekly_budget_cents"],
        budget_is_hard=c["budget_is_hard"],
        estimated_cost_cents=totals["cost_cents"],
        estimated_cost_display=money(totals["cost_cents"])
        + ("" if totals["cost_complete"] else " + unpriced items"),
        cost_complete=totals["cost_complete"],
        cost_note=f"Incomplete: no price yet for {', '.join(unpriced)}" if unpriced else None,
        store_totals=store_totals,
        cooking_minutes_total=sum(totals["hands_on_minutes"].values()),
        meals_count=totals["meals"],
        protein_g_week=week_protein,
        protein_g_per_day=(week_protein / n_days).quantize(Decimal("0.1"), ROUND_HALF_UP),
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
            )
            for b in batches
        ],
        warnings=list(report.get("warnings", [])),
        notes=list(report.get("notes", [])),
        generation_run_id=plan.generation_run_id,
    )


def accept(session: Session, user_id: int, plan_id: int) -> PlanSummaryOut:
    accept_plan(session, user_id, plan_id)
    return plan_summary(session, user_id, plan_id)


# ---------------- grocery list ----------------
def grocery_view(session: Session, user_id: int, plan_id: int, group_by_store: bool = True) -> GroceryListOut:
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
    names = {i: d.name for i, d in load_ingredients(session, {it.ingredient_id for it in items}).items()}
    stores = {s.id: s.name for s in session.scalars(select(Store))}
    products = {
        p.id: p.name
        for p in session.scalars(
            select(Product).where(Product.id.in_({it.product_id for it in items if it.product_id}))
        )
    }
    out_items = []
    for it in items:
        reason = it.reason or {}
        kind = reason.get("kind", "buy")
        to_buy_total = Decimal(reason.get("to_buy_total", it.to_buy_quantity))
        out_items.append(
            GroceryItemOut(
                id=it.id,
                ingredient_id=it.ingredient_id,
                name=names.get(it.ingredient_id, "?"),
                store_id=it.store_id,
                store_name=stores.get(it.store_id) if it.store_id else None,
                product_name=products.get(it.product_id) if it.product_id else None,
                needed=amount_display(it.needed_quantity, it.unit),
                from_inventory=amount_display(it.inventory_used_quantity, it.unit)
                if it.inventory_used_quantity
                else None,
                to_buy=(
                    f"{it.packages} × {products.get(it.product_id or 0, 'package')}"
                    if it.packages
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
                expected_remainder=amount_display(it.expected_remainder_quantity, it.unit)
                + " left (open package)"
                if it.expected_remainder_quantity
                else None,
                kind=kind,
                note=reason.get("note"),
            )
        )
    groups: dict[int | None, list[GroceryItemOut]] = defaultdict(list)
    for item in out_items:
        groups[item.store_id if group_by_store else None].append(item)
    primary_id = plan.constraints["store_ids"][0]
    order = sorted(groups, key=lambda sid: (sid is None, sid != primary_id, sid or 0))
    group_out = [
        GroceryGroupOut(
            store_id=sid,
            store_name=stores.get(sid, "Check you have / no price yet")
            if sid is not None
            else ("All items" if not group_by_store else "Check you have / no price yet"),
            subtotal_cents=sum(i.estimated_cost_cents or 0 for i in groups[sid]),
            items=groups[sid],
        )
        for sid in order
    ]
    totals = plan.totals
    threshold = plan.constraints["store_split_min_savings_cents"]
    split_info = totals.get("grocery", {})
    savings = int(split_info.get("savings_cents") or 0)
    split = any(i.store_id not in (None, primary_id) for i in out_items)
    note = None
    if split:
        others = sorted(
            {stores[i.store_id] for i in out_items if i.store_id is not None and i.store_id != primary_id}
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
        total_cents=totals["cost_cents"],
        total_display=money(totals["cost_cents"]),
        complete=totals["cost_complete"],
        unpriced=list(totals["unpriced"]),
        split=split,
        savings_cents=savings,
        split_threshold_cents=threshold,
        note=note,
        groups=group_out,
    )
