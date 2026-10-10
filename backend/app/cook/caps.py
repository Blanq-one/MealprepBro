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
