"""The week's money, from the rounded batches and the exact grocery plan (item 2 of the Phase 1 fix-up):

  cash          spent this trip on whole packages (the grocery list total): regular + stock-up
  eaten         food eaten this week, whether bought now or taken from inventory
  leftover      bought and not used this week; it carries into your inventory
  frozen        cooked extra portions frozen for later weeks
  expected waste  the at-risk part of the leftovers (perishable, no planned use, not raw protein you
                  freeze), plus inventory that expires this week unused

Purchases are valued at what you pay for them (package price over package amount); inventory at the
cheapest current price at your stores, since lots don't store what they cost. Always-have items (unlimited
stock you own) count as inventory at that price when there is one, and add nothing when there isn't.
Integer cents, each ingredient rounded once (§7.1), so cash + from_inventory = eaten + frozen + leftover
exactly.

Phase 2b: what each batch uses is split out of those ingredient amounts by largest remainder (by quantity),
then each batch's cost over its portions (meals first, in plan order, then the frozen extras), so meal costs
add up to their batch, and day costs (a day's meals) add up to food eaten, to the cent.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.domain.cost import round_cents, split_largest_remainder
from app.planning.perishables import leftover_fate, significant
from app.planning.problem import IngredientPlan
from app.planning.rounded import (
    CostSummary,
    GroceryItem,
    GroceryPlan,
    LeftoverItem,
    MealCost,
    RoundedBatch,
    RoundedMeal,
)
from app.schemas.constraints import PlanConstraints


def _inventory_rate(plan: IngredientPlan, store_ids: Sequence[int]) -> Decimal | None:
    rates = [o.cents_per_unit for o in plan.offers if o.store_id in store_ids]
    return min(rates) if rates else None


def _batch_quantities(
    batches: Sequence[RoundedBatch], ingredients: Mapping[int, IngredientPlan]
) -> dict[int, list[Decimal]]:
    """Per ingredient: what each batch uses of it (planning unit, counted lines), in batch order."""
    out: dict[int, list[Decimal]] = defaultdict(lambda: [Decimal(0)] * len(batches))
    for n, batch in enumerate(batches):
        for line in batch.lines:
            if line.optional:
                continue
            out[line.ingredient_id][n] += ingredients[line.ingredient_id].to_planning(
                line.base_quantity, line.base_unit
            )
    return out


def portion_split(
    batches: Sequence[RoundedBatch], meals: Sequence[RoundedMeal], batch_cents: Sequence[int]
) -> tuple[tuple[MealCost, ...], int]:
    """Each batch's cost over its portions by largest remainder: its meals (in plan order) first, then the
    extra portions frozen for later weeks. Returns the meal costs (in plan order) and the frozen extras'
    total."""
    meals_of: dict[int, list[int]] = defaultdict(list)
    for m, meal in enumerate(meals):
        meals_of[meal.batch_index].append(m)
    meal_cents: dict[int, int] = {}
    frozen = 0
    for n, batch in enumerate(batches):
        members = meals_of[n]
        extras = max(batch.portions - len(members), 0)
        parts = split_largest_remainder(batch_cents[n], [Decimal(1)] * (len(members) + extras))
        for m, cents in zip(members, parts, strict=False):
            meal_cents[m] = cents
        frozen += sum(parts[len(members) :])
    costs = tuple(
        MealCost(meal.eat_on, meal.slot.value, meal.batch_index, meal_cents.get(m, 0))
        for m, meal in enumerate(meals)
    )
    return costs, frozen


def cost_summary(
    c: PlanConstraints,
    batches: Sequence[RoundedBatch],
    grocery: GroceryPlan,
    ingredients: Mapping[int, IngredientPlan],
    meals: Sequence[RoundedMeal],
) -> tuple[CostSummary, tuple[LeftoverItem, ...]]:
    quantities = _batch_quantities(batches, ingredients)
    lines_by_ingredient: dict[int, list[GroceryItem]] = defaultdict(list)
    for item in grocery.items:
        lines_by_ingredient[item.ingredient_id].append(item)
    from_inventory = leftover = waste = 0
    batch_cents = [0] * len(batches)
    unpriced: list[str] = list(grocery.unpriced)
    leftovers: list[LeftoverItem] = []
    for ingredient_id in sorted(lines_by_ingredient):
        items = lines_by_ingredient[ingredient_id]
        first = items[0]
        if first.kind in ("staple", "unpriced"):
            continue
        plan = ingredients[ingredient_id]
        inventory_used = first.inventory_used
        inventory_cents = 0
        if inventory_used > 0:
            rate = _inventory_rate(plan, c.store_ids)
            if rate is not None:
                inventory_cents = round_cents(inventory_used * rate)
            elif first.kind != "always_have":  # an unpriced Always-have item simply isn't counted
                unpriced.append(f"{plan.name} (from inventory)")
        paid = sum(item.cost_cents or 0 for item in items)
        bought = sum((item.bought or Decimal(0) for item in items), Decimal(0))
        remainder = sum((item.remainder or Decimal(0) for item in items), Decimal(0))
        left_cents = round_cents(remainder * Decimal(paid) / bought) if bought > 0 and remainder > 0 else 0
        used = paid - left_cents + inventory_cents
        if used:
            for n, cents in enumerate(split_largest_remainder(used, quantities[ingredient_id])):
                batch_cents[n] += cents
        from_inventory += inventory_cents
        leftover += left_cents
        if remainder > 0 and significant(remainder, plan.planning_unit):
            fate = leftover_fate(plan, c)
            leftovers.append(
                LeftoverItem(ingredient_id, plan.name, plan.planning_unit, remainder, left_cents, fate)
            )
            if fate == "at_risk":
                waste += left_cents
    meal_costs, frozen = portion_split(batches, meals, batch_cents)
    taken = {lot_id for lot_id, _ in grocery.inventory_takes}
    for plan in ingredients.values():
        if plan.always_have:  # plans don't track Always-have lots
            continue
        rate = _inventory_rate(plan, c.store_ids)
        for lot in plan.lots:
            expiring = lot.expires_on is not None and lot.expires_on <= c.week_end
            frozen_lot = (lot.location or "fridge") == "freezer"
            if expiring and lot.id not in taken and rate is not None and not frozen_lot:
                waste += round_cents(lot.quantity * rate)
    summary = CostSummary(
        stock_up_cash_cents=grocery.stock_up_cents,
        cash_cents=grocery.total_cents,
        eaten_cents=sum(m.cents for m in meal_costs),
        from_inventory_cents=from_inventory,
        leftover_cents=leftover,
        frozen_portions_cents=frozen,
        expected_waste_cents=waste,
        complete=not unpriced,
        unpriced=tuple(unpriced),
        batch_cents=tuple(batch_cents),
        meal_costs=meal_costs,
    )
    return summary, tuple(leftovers)
