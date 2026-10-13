"""Classic and budget ingredients (the 2b.6 approval, item 4). Pure: no database.

A recipe line can name a budget equivalent of its (classic) ingredient from the same culinary role, with its
own amount (canned diced tomatoes for fresh ones in a curry). A budget tier plans with one side, by your
stores' real stored prices for the line's amount:

  Broke mode, Cheapest  the cheaper one ("canned diced tomatoes (classic: tomato)")
  A bit better          the classic, unless the budget one saves more than BETTER_KEEPS_CLASSIC a portion
  Fancy                 the classic
  no tier               the classic (the recipe as written)

A side the plan can't use (one the tier doesn't buy and your pantry lacks, or a food you don't eat) is never
picked; with either side unpriced, the classic stays. You can fix a line to one side for a recipe: that is
your own version of it (the line without its pair). Chicken forms stay exact (the seed pairs never name a
protein).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

from app.domain.price_tiers import PriceTier
from app.domain.units import ConversionError, convert
from app.planning.problem import IngredientPlan, RecipeLine

BETTER_KEEPS_CLASSIC = Decimal(25)  # cents a portion: a smaller saving keeps the classic in A bit better


def line_cents(
    plans: Mapping[int, IngredientPlan], ingredient_id: int, quantity: Decimal, unit: str
) -> Decimal | None:
    """What this much of an ingredient costs at your stores' cheapest unit price (None: no price)."""
    plan = plans.get(ingredient_id)
    if plan is None or not plan.offers:
        return None
    try:
        amount = convert(quantity, unit, plan.planning_unit, plan.units)
    except ConversionError:
        return None
    return amount * min(o.cents_per_unit for o in plan.offers)


def picks_budget(
    line: RecipeLine,
    tier: PriceTier | None,
    plans: Mapping[int, IngredientPlan],
    base_servings: int,
    usable: Callable[[int], bool],
) -> bool:
    """Whether a plan of this tier cooks the line with its budget equivalent."""
    alt = line.budget
    if alt is None or tier is None or not usable(alt.ingredient_id):
        return False
    if not usable(line.ingredient_id):
        return True  # the classic can't be had in this tier: the budget one stands in
    if tier is PriceTier.FANCY:
        return False
    classic = line_cents(plans, line.ingredient_id, line.quantity, line.unit)
    budget = line_cents(plans, alt.ingredient_id, alt.quantity, alt.unit)
    if classic is None or budget is None:
        return False
    saving = (classic - budget) / base_servings
    if saving <= 0:
        return False
    return saving > BETTER_KEEPS_CLASSIC if tier is PriceTier.BETTER else True


def as_budget(line: RecipeLine) -> RecipeLine:
    """The line cooked with its budget equivalent (same line id, its own amount), remembering the classic."""
    alt = line.budget
    assert alt is not None
    return replace(
        line,
        ingredient_id=alt.ingredient_id,
        quantity=alt.quantity,
        unit=alt.unit,
        authored_quantity=alt.authored_quantity,
        authored_unit=alt.authored_unit,
        classic_ingredient_id=line.ingredient_id,
    )


def choose_lines(
    lines: Sequence[RecipeLine],
    tier: PriceTier | None,
    plans: Mapping[int, IngredientPlan],
    base_servings: int,
    usable: Callable[[int], bool],
    *,
    pinned: frozenset[int] | None = None,
) -> list[RecipeLine]:
    """The recipe's lines as this tier cooks them. `pinned` (a swap keeping a stored batch): exactly these
    line ids on their budget side, as the batch was planned, whatever the prices say now."""
    out = []
    for line in lines:
        if line.budget is None:
            out.append(line)
            continue
        if pinned is not None:
            budget = line.recipe_ingredient_id in pinned
        else:
            budget = picks_budget(line, tier, plans, base_servings, usable)
        out.append(as_budget(line) if budget else line)
    return out
