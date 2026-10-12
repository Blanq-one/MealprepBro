"""Seed recipe drafts with computed nutrition and cost, and rendered recipe versions at any portion count.
A prep item's page carries its stages and how it keeps after each, an assembly's its items, add-ons and
eating-day instruction, with its numbers its items' portions plus its add-ons (step 2b.10)."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Recipe, RecipeFamily, RecipeIngredient, RecipeStep, RecipeVersion
from app.domain.enums import PortionSize, RecipeKind, RecipeOrigin
from app.domain.nutrition import NutritionTotals
from app.domain.quantities import display_unit
from app.domain.scaling import PORTION_MULTIPLIERS
from app.domain.units import ConversionError, UnitError, convert, grams_of
from app.planning.assemblies import Assembly, ItemPortion, item_portion, load_assembly
from app.planning.reference import daily_values
from app.planning.rendering import LineInput as RenderLine
from app.planning.rendering import RenderedRecipe, RenderInput, StepInput, render
from app.services.calculations import (
    LineInput,
    LineResult,
    RecipeCalculation,
    ScaledCalculation,
    calculate,
    calculate_scaled,
)
from app.services.ingredient_data import IngredientData, load_ingredients
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
    item: ItemPortion | None = None  # a prep item: its stages and storage (step 2b.10)
    assembly: Assembly | None = None  # an assembly: its items, add-ons, name and instruction


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
            Recipe.user_id == user_id,
            Recipe.origin == RecipeOrigin.SEED.value,
            Recipe.archived_at.is_(None),
            # dishes and prep items; an assembly's numbers are its items' (its recipe page)
            RecipeVersion.kind != RecipeKind.ASSEMBLY.value,
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


def shown_in(amount: Decimal, unit: str, d: IngredientData) -> tuple[Decimal, str]:
    """A line as you measure it: scoop-based items always in scoops (A1)."""
    wanted = display_unit(unit, dict(d.units.named_units))
    if wanted == unit:
        return amount, unit
    try:
        return convert(amount, unit, wanted, d.units).quantize(Decimal("0.01")), wanted
    except (ConversionError, UnitError):
        return amount, unit


def _render_lines(session: Session, version_id: int, scaled: ScaledCalculation) -> list[RenderLine]:
    rows = list(
        session.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_version_id == version_id)
            .order_by(RecipeIngredient.position)
        )
    )
    data = load_ingredients(session, [r.ingredient_id for r in rows])
    out = []
    for row, line, result in zip(rows, scaled.scaled, scaled.calculation.lines, strict=True):
        d = data[row.ingredient_id]
        amount, unit = shown_in(line.amount, line.unit, d)
        out.append(
            RenderLine(
                row.ingredient_id,
                d.name,
                amount,
                unit,
                grams_of(result.quantity, result.unit, d.units) * d.profile.edible_fraction,  # M5
                row.role,
                d.safety_category,
                row.preparation,
                row.is_optional,
            )
        )
    return out


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
    settings = load_settings(session, user_id)
    if version.kind == RecipeKind.ASSEMBLY.value:
        return _assembly_view(
            session,
            user_id,
            version,
            recipe,
            portions=n,
            size=size,
            leftover_fridge_days=settings.leftover_fridge_days,
        )
    lines = version_lines(session, version.id)
    scaled = calculate_scaled(session, lines, version.base_servings, n, PORTION_MULTIPLIERS[size.value])
    calc = scaled.calculation
    steps = [
        StepInput(
            s.section, s.text, s.duration_minutes, s.appliance_temp_f, s.doneness_check_ingredient_id, s.stage
        )
        for s in session.scalars(
            select(RecipeStep).where(RecipeStep.recipe_version_id == version.id).order_by(RecipeStep.position)
        )
    ]
    item = None
    if version.kind == RecipeKind.PREP_ITEM.value:
        item = item_portion(session, version, recipe, leftover_fridge_days=settings.leftover_fridge_days)
    heme = calc.per_portion.heme.heme_mg if calc.per_portion.heme else None
    rendered = render(
        RenderInput(
            version.id,
            version.title,
            version.description,
            version.is_draft,
            version.freezer_friendly,
            n,
            _render_lines(session, version.id, scaled),
            steps,
            settings.leftover_fridge_days,
            calc.per_portion.amounts,
            daily_values(session),
            heme,
            storage_text=item.storage[-1].note if item is not None else None,
        )
    )
    return VersionView(version, recipe, n, size, rendered, calc, item=item)


def _assembly_view(
    session: Session,
    user_id: int,
    version: RecipeVersion,
    recipe: Recipe,
    *,
    portions: int,
    size: PortionSize,
    leftover_fridge_days: int,
) -> VersionView:
    """An assembly is per portion: its items' portions plus its add-ons (its own lines, base servings 1)."""
    assembly = load_assembly(session, user_id, version, leftover_fridge_days=leftover_fridge_days)
    lines = version_lines(session, version.id)
    render_lines: list[RenderLine] = []
    line_results: tuple[LineResult, ...] = ()
    if lines:
        scaled = calculate_scaled(session, lines, 1, portions)
        render_lines = _render_lines(session, version.id, scaled)
        line_results = scaled.calculation.lines
    per = assembly.per_portion
    reasons = [r for p in assembly.parts for r in p.item.calculation.incomplete_reasons]
    if assembly.add_on_calculation is not None:
        reasons += assembly.add_on_calculation.incomplete_reasons
    calc = RecipeCalculation(
        portions=portions,
        lines=line_results,
        totals=NutritionTotals({k: v * portions for k, v in per.amounts.items()}, per.missing),
        per_portion=per,
        costs=assembly.costs,
        optional_not_counted=(),
        incomplete_reasons=tuple(dict.fromkeys(reasons)),
    )
    rendered = render(
        RenderInput(
            version.id,
            assembly.name,
            version.description,
            version.is_draft,
            False,
            portions,
            render_lines,
            [],
            leftover_fridge_days,
            per.amounts,
            daily_values(session),
            per.heme.heme_mg if per.heme else None,
        )
    )
    return VersionView(version, recipe, portions, size, rendered, calc, assembly=assembly)


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
