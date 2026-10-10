"""Write a validated RoundedPlan: meal_plan, cook batches, practical batch quantities, meals and the
grocery list."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import (
    GroceryList,
    GroceryListItem,
    MealPlan,
    PlanBatchIngredient,
    PlanCookBatch,
    PlanMeal,
)
from app.planning.plan_validator import ValidationReport
from app.planning.rounded import RoundedPlan

_Q3 = Decimal("0.001")


class PlanNotFoundError(LookupError):
    pass


def save_plan(
    session: Session,
    user_id: int,
    plan: RoundedPlan,
    report: ValidationReport,
    run_id: int | None,
    *,
    kind: str | None = None,
) -> MealPlan:
    """`kind` (Phase 2b): meal_prep | single | grocery_advice; None = a week plan from POST /plans."""
    c = plan.constraints
    validation = report.to_json()
    validation["notes"] = list(plan.notes)
    row = MealPlan(
        user_id=user_id,
        week_start=c.week_start,
        status="draft",
        constraints=c.canonical(),
        constraints_hash=c.content_hash(),
        generation_run_id=run_id,
        solver_status=plan.solver_status,
        solver_objective=Decimal(str(round(plan.solver_objective, 6))),
        totals={
            **plan.totals.to_json(),
            "grocery": {
                "split": plan.grocery.split,
                "savings_cents": plan.grocery.savings_cents,
                "primary_only_cents": plan.grocery.primary_only_cents,
                "forced_elsewhere": list(plan.grocery.forced_elsewhere),
                "stock_up_cents": plan.grocery.stock_up_cents,
            },
            "costs": plan.costs.to_json(),
            "leftovers": [item.to_json() for item in plan.leftovers],
            "freeze": [item.to_json() for item in plan.freeze],
        },
        validation_report=validation,
        kind=kind,
    )
    session.add(row)
    session.flush()
    batch_ids: list[int] = []
    for batch in plan.batches:
        b = PlanCookBatch(
            meal_plan_id=row.id,
            recipe_version_id=batch.version_id,
            cook_on=batch.cook_on,
            portions=batch.portions,
            portions_to_freeze=batch.portions_to_freeze,
            portion_size=batch.portion_size.value,
            portion_multiplier=batch.portion_multiplier.quantize(_Q3),
            scale_factor=batch.scale_factor,
            planned_minutes=batch.planned_minutes,
        )
        session.add(b)
        session.flush()
        batch_ids.append(b.id)
        for line in batch.lines:
            session.add(
                PlanBatchIngredient(
                    cook_batch_id=b.id,
                    recipe_ingredient_id=line.recipe_ingredient_id,
                    ingredient_id=line.ingredient_id,
                    quantity=line.base_quantity,
                    unit=line.base_unit,
                    adjustment=line.adjustment,
                )
            )
    for meal in plan.meals:
        session.add(
            PlanMeal(
                meal_plan_id=row.id,
                eat_on=meal.eat_on,
                slot=meal.slot.value,
                cook_batch_id=batch_ids[meal.batch_index],
                from_freezer=meal.from_freezer,
                planned_kcal=meal.kcal,
            )
        )
    grocery = GroceryList(user_id=user_id, meal_plan_id=row.id, mode=c.grocery_mode.value, status="open")
    session.add(grocery)
    session.flush()
    listed = [item for item in plan.grocery.items if item.kind != "always_have"]  # never listed
    for position, item in enumerate(listed, start=1):
        session.add(
            GroceryListItem(
                grocery_list_id=grocery.id,
                position=position,
                ingredient_id=item.ingredient_id,
                product_id=item.product_id,
                store_id=item.store_id,
                needed_quantity=item.needed.quantize(_Q3),
                inventory_used_quantity=item.inventory_used.quantize(_Q3),
                to_buy_quantity=(item.bought if item.bought is not None else item.to_buy).quantize(_Q3),
                expected_remainder_quantity=item.remainder.quantize(_Q3)
                if item.remainder is not None
                else None,
                unit=item.unit,
                packages=item.packages,
                estimated_cost_cents=item.cost_cents,
                price_observation_id=item.observation_id,
                reason={
                    "kind": item.kind,
                    "recipes": list(item.recipes),
                    "note": item.note,
                    "is_estimate": item.is_estimate,
                    "perishable": item.perishable,
                    "stock_up": item.stock_up,
                    "to_buy_total": str(item.to_buy.quantize(_Q3)),
                },
            )
        )
    session.flush()
    return row


def accept_plan(session: Session, user_id: int, plan_id: int) -> MealPlan:
    """Make a draft the week's active plan; any earlier active plan for that week becomes superseded."""
    plan = session.get(MealPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise PlanNotFoundError(f"plan {plan_id} not found")
    if plan.status == "active":
        return plan
    previous = session.scalars(
        select(MealPlan).where(
            MealPlan.user_id == user_id, MealPlan.week_start == plan.week_start, MealPlan.status == "active"
        )
    ).first()
    if previous is not None:
        session.execute(update(MealPlan).where(MealPlan.id == previous.id).values(status="superseded"))
        plan.supersedes_plan_id = previous.id
        session.flush()
    plan.status = "active"
    plan.accepted_at = datetime.now(UTC)
    session.flush()
    return plan
