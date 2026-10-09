"""Seed recipe drafts with computed nutrition and cost."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Recipe, RecipeFamily, RecipeIngredient, RecipeVersion
from app.domain.enums import RecipeOrigin
from app.services.calculations import LineInput, RecipeCalculation, calculate


@dataclass(frozen=True)
class SeedRecipeView:
    recipe: Recipe
    version: RecipeVersion
    family: str | None
    calculation: RecipeCalculation


def version_lines(session: Session, version_id: int) -> list[LineInput]:
    rows = session.scalars(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_version_id == version_id)
        .order_by(RecipeIngredient.position)
    )
    return [LineInput(r.ingredient_id, r.quantity, r.unit, r.is_optional) for r in rows]


def seed_recipes(session: Session, user_id: int) -> list[SeedRecipeView]:
    rows = session.execute(
        select(Recipe, RecipeVersion, RecipeFamily.name)
        .join(RecipeVersion, RecipeVersion.id == Recipe.default_version_id)
        .outerjoin(RecipeFamily, RecipeFamily.id == Recipe.family_id)
        .where(
            Recipe.user_id == user_id, Recipe.origin == RecipeOrigin.SEED.value, Recipe.archived_at.is_(None)
        )
        .order_by(Recipe.id)
    ).all()
    return [
        SeedRecipeView(
            recipe,
            version,
            family,
            calculate(session, version_lines(session, version.id), version.base_servings),
        )
        for recipe, version, family in rows
    ]
