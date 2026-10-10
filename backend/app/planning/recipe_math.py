"""Recipe numbers for planning, computed by code from stored lines and per-100 g values
(CLAUDE.md rules 1, 3).

Shared by the problem loader (exact, unrounded per-portion values for the solver), the post-solve rounding
(values from the practical, rounded quantities) and the test factories.
"""

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal

from app.domain.nutrition import NutritionLine, NutritionTotals, divide, total
from app.domain.units import grams_of
from app.planning.problem import IngredientPlan, RecipeLine

PLANNING_CODES: tuple[str, ...] = (
    "energy_kcal",
    "protein_g",
    "carbohydrate_g",
    "fat_g",
    "fiber_g",
    "iron_mg",
)


def counted(lines: Iterable[RecipeLine]) -> list[RecipeLine]:
    """Optional lines (garnishes, toppings) are listed but never counted (Phase 0 cost/nutrition rule)."""
    return [line for line in lines if not line.optional]


def nutrition_of(
    amounts: Sequence[tuple[int, Decimal, str]],
    ingredients: Mapping[int, IngredientPlan],
    codes: Sequence[str] = PLANNING_CODES,
) -> NutritionTotals:
    """Totals for (ingredient id, quantity, base unit) lines."""
    lines = [
        NutritionLine(ingredients[i].profile, grams_of(q, unit, ingredients[i].units))
        for i, q, unit in amounts
    ]
    return total(lines, codes)


def recipe_per_portion(
    lines: Sequence[RecipeLine],
    ingredients: Mapping[int, IngredientPlan],
    base_servings: int,
    codes: Sequence[str] = PLANNING_CODES,
) -> NutritionTotals:
    amounts = [(line.ingredient_id, line.quantity, line.unit) for line in counted(lines)]
    return divide(nutrition_of(amounts, ingredients, codes), base_servings)


def need_per_portion(
    lines: Sequence[RecipeLine], ingredients: Mapping[int, IngredientPlan], base_servings: int
) -> dict[int, Decimal]:
    """What one portion (multiplier 1) uses of each ingredient the plan has to supply (not staples or
    Always-have items), in its planning unit."""
    need: dict[int, Decimal] = {}
    for line in counted(lines):
        plan = ingredients[line.ingredient_id]
        if plan.unlimited:
            continue
        need[line.ingredient_id] = need.get(line.ingredient_id, Decimal(0)) + plan.to_planning(
            line.quantity, line.unit
        ) / Decimal(base_servings)
    return need


def cost_per_portion(
    need: Mapping[int, Decimal], ingredients: Mapping[int, IngredientPlan]
) -> Decimal | None:
    """Cents per portion at the lowest unit price among the offers; None if anything is unpriced. Used only to
    neutralize never-favored recipes' price advantage, never shown."""
    cents = Decimal(0)
    for ingredient_id, quantity in need.items():
        offers = ingredients[ingredient_id].offers
        if not offers:
            return None
        cents += quantity * min(o.cents_per_unit for o in offers)
    return cents
