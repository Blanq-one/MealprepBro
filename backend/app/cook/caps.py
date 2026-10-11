"""Frequency caps per calendar week (FLOW_SPEC §13.3, change F7; Q6): "pork ≤ 1 meal a week" counts Monday to
Sunday in your timezone, across your active plans and your one-meal plans, so rolling plans and single meals
don't each get their own allowance.

A meal counts once if any ingredient of its batch's recipe is a member. A one-meal plan counts when it was
cooked, or while it is still planned for today or later (an old one never cooked was abandoned).
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import MealPlan, PlanCookBatch, PlanMeal, RecipeIngredient
from app.domain.frequency_caps import ResolvedCap


def week_of(day: date) -> tuple[date, date]:
    """The Monday–Sunday week that contains `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def meals_this_week(
    session: Session, user_id: int, caps: Iterable[ResolvedCap], today: date
) -> dict[str, int]:
    """Meals this calendar week that count toward each cap (by label)."""
    caps = [cap for cap in caps if cap.max_meals_per_week > 0]
    if not caps:
        return {}
    monday, sunday = week_of(today)
    single = and_(
        MealPlan.kind == "single",
        or_(
            PlanCookBatch.status == "cooked",
            and_(PlanCookBatch.status == "planned", PlanMeal.eat_on >= today),
        ),
    )
    rows = session.execute(
        select(PlanMeal.id, PlanCookBatch.recipe_version_id)
        .join(PlanCookBatch, PlanCookBatch.id == PlanMeal.cook_batch_id)
        .join(MealPlan, MealPlan.id == PlanMeal.meal_plan_id)
        .where(
            MealPlan.user_id == user_id,
            PlanMeal.eat_on >= monday,
            PlanMeal.eat_on <= sunday,
            PlanMeal.status.notin_(("replaced", "skipped")),
            or_(MealPlan.status == "active", single),  # a one-meal plan is never active
        )
    ).all()
    versions = {version_id for _, version_id in rows}
    ingredients: Mapping[int, set[int]] = defaultdict(set)
    if versions:
        for version_id, ingredient_id in session.execute(
            select(RecipeIngredient.recipe_version_id, RecipeIngredient.ingredient_id).where(
                RecipeIngredient.recipe_version_id.in_(versions)
            )
        ).tuples():
            ingredients[version_id].add(ingredient_id)
    return {
        cap.label: sum(1 for _, version_id in rows if ingredients[version_id] & cap.member_ids)
        for cap in caps
    }


def used_up(caps: Iterable[ResolvedCap], used: Mapping[str, int]) -> dict[str, frozenset[int]]:
    """Caps whose allowance this week is used up: label -> members (filtered from the ranking)."""
    return {
        cap.label: cap.member_ids
        for cap in caps
        if cap.max_meals_per_week > 0 and used.get(cap.label, 0) >= cap.max_meals_per_week
    }


def plan_days(plan: MealPlan) -> tuple[date, date]:
    """A stored plan's first and last day."""
    days = len(plan.constraints.get("days", [])) or 7
    return plan.week_start, plan.week_start + timedelta(days=days - 1)


def week_use(
    session: Session, user_id: int, caps: Iterable[ResolvedCap], *, start: date, end: date, today: date
) -> dict[tuple[date, str], int]:
    """For a new plan from `start` to `end`: meals your other plans count toward each cap, per Monday–Sunday
    week it touches, by (Monday, label). Active plans count unless they overlap the new plan (accepting it
    replaces them); one-meal plans count as in meals_this_week."""
    caps = [cap for cap in caps if cap.max_meals_per_week > 0]
    if not caps:
        return {}
    first, last = week_of(start)[0], week_of(end)[1]
    single = and_(
        MealPlan.kind == "single",
        or_(
            PlanCookBatch.status == "cooked",
            and_(PlanCookBatch.status == "planned", PlanMeal.eat_on >= today),
        ),
    )
    rows = session.execute(
        select(PlanMeal.eat_on, PlanCookBatch.recipe_version_id, MealPlan)
        .join(PlanCookBatch, PlanCookBatch.id == PlanMeal.cook_batch_id)
        .join(MealPlan, MealPlan.id == PlanMeal.meal_plan_id)
        .where(
            MealPlan.user_id == user_id,
            PlanMeal.eat_on >= first,
            PlanMeal.eat_on <= last,
            PlanMeal.status.notin_(("replaced", "skipped")),
            or_(MealPlan.status == "active", single),
        )
    ).all()
    kept = []
    for eat_on, version_id, plan in rows:
        if plan.kind != "single":
            plan_start, plan_end = plan_days(plan)
            if plan_start <= end and start <= plan_end:
                continue  # overlaps the new plan: accepting it replaces this one
        kept.append((eat_on, version_id))
    versions = {version_id for _, version_id in kept}
    ingredients: Mapping[int, set[int]] = defaultdict(set)
    if versions:
        for version_id, ingredient_id in session.execute(
            select(RecipeIngredient.recipe_version_id, RecipeIngredient.ingredient_id).where(
                RecipeIngredient.recipe_version_id.in_(versions)
            )
        ).tuples():
            ingredients[version_id].add(ingredient_id)
    out: dict[tuple[date, str], int] = defaultdict(int)
    for eat_on, version_id in kept:
        for cap in caps:
            if ingredients[version_id] & cap.member_ids:
                out[(week_of(eat_on)[0], cap.label)] += 1
    return dict(out)
