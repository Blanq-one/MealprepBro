"""Dish categories of stored recipe versions (the pure classifier is domain/dish_category.py)."""

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RecipeIngredient, RecipeVersion
from app.domain.dish_category import DishCategory, DishLine, classify
from app.domain.units import UnitError, grams_of
from app.services.ingredient_data import load_ingredients


def dish_categories(session: Session, version_ids: Iterable[int]) -> dict[int, DishCategory]:
    ids = sorted(set(version_ids))
    if not ids:
        return {}
    rows = list(
        session.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_version_id.in_(ids))
            .order_by(RecipeIngredient.recipe_version_id, RecipeIngredient.position)
        )
    )
    data = load_ingredients(session, {r.ingredient_id for r in rows})
    lines: dict[int, list[DishLine]] = defaultdict(list)
    for r in rows:
        d = data[r.ingredient_id]
        try:
            grams = grams_of(r.quantity, r.unit, d.units)
        except UnitError:
            grams = Decimal(0)  # a count without a piece weight: weight unknown
        lines[r.recipe_version_id].append(DishLine(d.name, r.role, grams, r.is_optional))
    return {
        v.id: classify(v.title, v.meal_slots, lines[v.id], v.equipment)
        for v in session.scalars(select(RecipeVersion).where(RecipeVersion.id.in_(ids)))
    }
