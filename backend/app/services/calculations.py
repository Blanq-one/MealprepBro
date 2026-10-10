"""Recipe nutrition and cost, computed by code from stored per-100 g values and per-store prices."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import Store
from app.domain.cost import CostLine, CostTotal, consumed_cost, per_portion_cents
from app.domain.enums import NutritionSource
from app.domain.nutrition import CORE_CODES, NutritionLine, NutritionTotals, divide, total
from app.domain.scaling import ScaledLine, scale_factor, scale_line
from app.domain.units import grams_of, normalize_unit, to_base
from app.services.ingredient_data import IngredientData, load_ingredients, nutrient_codes
from app.services.pricing import StorePrice, active_stores, best_price_at_store, current_prices


class CalculationError(ValueError):
    pass


@dataclass(frozen=True)
class CalcContext:
    """Everything `calculate` reads from the database, loaded once for many recipes (the meal-now cards).
    A calculation with a context gives exactly the numbers it gives without one."""

    data: dict[int, IngredientData]
    codes: list[str]
    prices: list[StorePrice]
    grocery_stores: list[Store]
    other_store_ids: list[int]


def load_context(session: Session, ingredient_ids: Iterable[int]) -> CalcContext:
    ids = set(ingredient_ids)
    return CalcContext(
        data=load_ingredients(session, ids),
        codes=nutrient_codes(session),
        prices=current_prices(session, ids),
        grocery_stores=active_stores(session, "grocery"),
        other_store_ids=[s.id for s in active_stores(session, "other")],
    )


@dataclass(frozen=True)
class LineInput:
    ingredient_id: int
    quantity: Decimal
    unit: str
    optional: bool = False


@dataclass(frozen=True)
class LineResult:
    ingredient: IngredientData
    quantity: Decimal  # base units
    unit: str
    grams: Decimal
    optional: bool
    authored_quantity: Decimal  # as written, for display
    authored_unit: str


@dataclass(frozen=True)
class StoreCost:
    store_id: int
    store_name: str
    total: CostTotal
    per_portion_cents: int
    uses_estimates: bool


@dataclass(frozen=True)
class RecipeCalculation:
    portions: int
    lines: tuple[LineResult, ...]
    totals: NutritionTotals
    per_portion: NutritionTotals
    costs: tuple[StoreCost, ...]
    optional_not_counted: tuple[str, ...]
    incomplete_reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def nutrition_complete(self) -> bool:
        return self.totals.core_complete


def _resolve(lines: Sequence[LineInput], data: dict[int, IngredientData]) -> list[LineResult]:
    results = []
    for line in lines:
        ingredient = data.get(line.ingredient_id)
        if ingredient is None:
            raise CalculationError(f"unknown ingredient id {line.ingredient_id}")
        unit = normalize_unit(line.unit, ingredient.units.named_units)
        base = to_base(line.quantity, unit, ingredient.units)
        grams = grams_of(base.amount, base.unit.value, ingredient.units)
        results.append(
            LineResult(ingredient, base.amount, base.unit.value, grams, line.optional, line.quantity, unit)
        )
    return results


def _label_reason(data: IngredientData, missing: Sequence[str]) -> str:
    if data.nutrition_source == NutritionSource.PACKAGE_LABEL:
        return f"incomplete: {data.name} label values missing ({', '.join(missing)})"
    return f"incomplete: {data.name} has no {', '.join(missing)} in its nutrition source"


def calculate(
    session: Session, lines: Sequence[LineInput], portions: int, *, context: CalcContext | None = None
) -> RecipeCalculation:
    if portions < 1:
        raise CalculationError("portions must be at least 1")
    if not lines:
        raise CalculationError("a recipe needs at least one ingredient line")
    if context is None:
        context = load_context(session, [line.ingredient_id for line in lines])
    resolved = _resolve(lines, context.data)
    counted = [r for r in resolved if not r.optional]
    totals = total([NutritionLine(r.ingredient.profile, r.grams) for r in counted], context.codes)

    reasons: list[str] = []
    for r in counted:
        missing_core = [c for c in CORE_CODES if c not in r.ingredient.profile.per_100g]
        if missing_core:
            reasons.append(_label_reason(r.ingredient, missing_core))

    counted_ids = {r.ingredient.id for r in counted}
    prices = [p for p in context.prices if p.ingredient_id in counted_ids]
    others = context.other_store_ids
    costs = []
    for store in context.grocery_stores:
        cost_lines = []
        estimates = False
        for r in counted:
            best = best_price_at_store(prices, r.ingredient.id, store.id, r.unit, r.ingredient.units)
            if best is None:  # not carried here: priced where it comes from (protein powder at "Other")
                options = [
                    o
                    for sid in others
                    if (o := best_price_at_store(prices, r.ingredient.id, sid, r.unit, r.ingredient.units))
                ]
                best = min(options, key=lambda pc: pc[1]) if options else None
            if best is not None and best[0].is_estimate:
                estimates = True
            cost_lines.append(
                CostLine(
                    r.ingredient.name,
                    r.quantity,
                    best[1] if best else None,
                    is_staple=r.ingredient.assume_in_stock,
                )
            )
        cost = consumed_cost(cost_lines)
        costs.append(
            StoreCost(store.id, store.name, cost, per_portion_cents(cost.cents, portions), estimates)
        )

    return RecipeCalculation(
        portions=portions,
        lines=tuple(resolved),
        totals=totals,
        per_portion=divide(totals, portions),
        costs=tuple(costs),
        optional_not_counted=tuple(r.ingredient.name for r in resolved if r.optional),
        incomplete_reasons=tuple(dict.fromkeys(reasons)),
    )


@dataclass(frozen=True)
class ScaledCalculation:
    factor: Decimal
    scaled: tuple[ScaledLine, ...]  # practical (rounded) amounts, aligned with calculation.lines
    calculation: RecipeCalculation


def calculate_scaled(
    session: Session,
    lines: Sequence[LineInput],
    base_servings: int,
    portions: int,
    portion_multiplier: Decimal = Decimal(1),
    *,
    context: CalcContext | None = None,
) -> ScaledCalculation:
    """Scale to `portions`, round every line to a practical amount, then compute nutrition and cost
    from the ROUNDED amounts (BUILD_PLAN §2.5)."""
    factor = scale_factor(base_servings, portions, portion_multiplier)
    if context is None:
        context = load_context(session, [line.ingredient_id for line in lines])
    scaled: list[ScaledLine] = []
    practical: list[LineInput] = []
    for line in lines:
        ingredient = context.data.get(line.ingredient_id)
        if ingredient is None:
            raise CalculationError(f"unknown ingredient id {line.ingredient_id}")
        unit = normalize_unit(line.unit, ingredient.units.named_units)
        result = scale_line(line.quantity, unit, factor, ingredient.count_rounding_step)
        scaled.append(result)
        practical.append(LineInput(line.ingredient_id, result.amount, result.unit, line.optional))
    return ScaledCalculation(factor, tuple(scaled), calculate(session, practical, portions, context=context))
