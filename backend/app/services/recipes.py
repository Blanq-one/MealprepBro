"""Seed recipe drafts with computed nutrition and cost, and rendered recipe versions at any portion count."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Recipe, RecipeFamily, RecipeIngredient, RecipeStep, RecipeVersion
from app.domain.enums import PortionSize, RecipeOrigin
from app.domain.scaling import PORTION_MULTIPLIERS
from app.domain.units import grams_of
from app.planning.reference import daily_values
from app.planning.rendering import LineInput as RenderLine
from app.planning.rendering import RenderedRecipe, RenderInput, StepInput, render
from app.services.calculations import LineInput, RecipeCalculation, calculate, calculate_scaled
from app.services.ingredient_data import load_ingredients
from app.services.settings import load_settings


class RecipeNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class VersionView:
    version: RecipeVersion
    recipe: Recipe
    portions: int
    portion_size: PortionSize
    rendered: RenderedRecipe
    calculation: RecipeCalculation


@dataclass(frozen=True)
class RecipeView:
    recipe: Recipe
    family: str | None
    versions: list[RecipeVersion]
    default: VersionView | None


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
    return [LineInput(r.ingredient_id, r.authored_quantity, r.authored_unit, r.is_optional) for r in rows]


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


def _version(session: Session, user_id: int, version_id: int) -> tuple[RecipeVersion, Recipe]:
    row = session.execute(
        select(RecipeVersion, Recipe)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .where(RecipeVersion.id == version_id)
    ).first()
    if row is None or row[1].user_id != user_id:
        raise RecipeNotFoundError(f"recipe version {version_id} not found")
    return row[0], row[1]


def version_view(
    session: Session,
    user_id: int,
    version_id: int,
    portions: int | None = None,
    portion_size: PortionSize | None = None,
) -> VersionView:
    version, recipe = _version(session, user_id, version_id)
    size = portion_size or PortionSize.NORMAL
    n = portions or version.base_servings
    lines = version_lines(session, version.id)
    scaled = calculate_scaled(session, lines, version.base_servings, n, PORTION_MULTIPLIERS[size.value])
    calc = scaled.calculation
    rows = list(
        session.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_version_id == version.id)
            .order_by(RecipeIngredient.position)
        )
    )
    data = load_ingredients(session, [r.ingredient_id for r in rows])
    render_lines = []
    for row, line, result in zip(rows, scaled.scaled, calc.lines, strict=True):
        d = data[row.ingredient_id]
        render_lines.append(
            RenderLine(
                row.ingredient_id,
                d.name,
                line.amount,
                line.unit,
                grams_of(result.quantity, result.unit, d.units),
                row.role,
                d.safety_category,
                row.preparation,
                row.is_optional,
            )
        )
    steps = [
        StepInput(s.section, s.text, s.duration_minutes, s.appliance_temp_f, s.doneness_check_ingredient_id)
        for s in session.scalars(
            select(RecipeStep).where(RecipeStep.recipe_version_id == version.id).order_by(RecipeStep.position)
        )
    ]
    settings = load_settings(session, user_id)
    heme = calc.per_portion.heme.heme_mg if calc.per_portion.heme else None
    rendered = render(
        RenderInput(
            version.id,
            version.title,
            version.description,
            version.is_draft,
            version.freezer_friendly,
            n,
            render_lines,
            steps,
            settings.leftover_fridge_days,
            calc.per_portion.amounts,
            daily_values(session),
            heme,
        )
    )
    return VersionView(version, recipe, n, size, rendered, calc)


def recipe_view(session: Session, user_id: int, recipe_id: int) -> RecipeView:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise RecipeNotFoundError(f"recipe {recipe_id} not found")
    family = session.get(RecipeFamily, recipe.family_id) if recipe.family_id else None
    versions = list(
        session.scalars(
            select(RecipeVersion)
            .where(RecipeVersion.recipe_id == recipe.id)
            .order_by(RecipeVersion.version_number)
        )
    )
    default = version_view(session, user_id, recipe.default_version_id) if recipe.default_version_id else None
    return RecipeView(recipe, family.name if family else None, versions, default)
