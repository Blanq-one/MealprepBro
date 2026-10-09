"""The week's money, from the rounded batches and the exact grocery plan (item 2 of the Phase 1 fix-up):

  cash          spent this trip on whole packages (the grocery list total): regular + stock-up
  eaten         food eaten this week, whether bought now or taken from inventory
  leftover      bought and not used this week; it carries into your inventory
  frozen        cooked extra portions frozen for later weeks
  expected waste  the at-risk part of the leftovers (perishable, no planned use, not raw protein you
                  freeze), plus inventory that expires this week unused

Purchases are valued at what you pay for them (package price over package amount); inventory at the
cheapest current price at your stores, since lots don't store what they cost. Integer cents, each
ingredient rounded once (§7.1), so cash + from_inventory = eaten + frozen + leftover exactly.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.domain.cost import round_cents
from app.planning.perishables import leftover_fate, significant
from app.planning.problem import IngredientPlan
from app.planning.rounded import CostSummary, GroceryItem, GroceryPlan, LeftoverItem, RoundedBatch
from app.schemas.constraints import PlanConstraints


def _inventory_rate(plan: IngredientPlan, store_ids: Sequence[int]) -> Decimal | None:
    rates = [o.cents_per_unit for o in plan.offers if o.store_id in store_ids]
    return min(rates) if rates else None


def _eaten_share(
    batches: Sequence[RoundedBatch], ingredients: Mapping[int, IngredientPlan]
) -> dict[int, Decimal]:
    """Per ingredient: the share of this week's use that is eaten this week (the rest is in frozen
    extra portions)."""
    total: dict[int, Decimal] = defaultdict(Decimal)
    eaten: dict[int, Decimal] = defaultdict(Decimal)
    for batch in batches:
        share = Decimal(batch.portions - batch.portions_to_freeze) / Decimal(batch.portions)
        for line in batch.lines:
            if line.optional:
                continue
            quantity = ingredients[line.ingredient_id].to_planning(line.base_quantity, line.base_unit)
            total[line.ingredient_id] += quantity
            eaten[line.ingredient_id] += quantity * share
    return {i: (eaten[i] / total[i] if total[i] > 0 else Decimal(1)) for i in total}


def cost_summary(
    c: PlanConstraints,
    batches: Sequence[RoundedBatch],
    grocery: GroceryPlan,
    ingredients: Mapping[int, IngredientPlan],
) -> tuple[CostSummary, tuple[LeftoverItem, ...]]:
    share = _eaten_share(batches, ingredients)
    lines_by_ingredient: dict[int, list[GroceryItem]] = defaultdict(list)
    for item in grocery.items:
        lines_by_ingredient[item.ingredient_id].append(item)
    eaten = from_inventory = leftover = frozen = waste = 0
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
            if rate is None:
                unpriced.append(f"{plan.name} (from inventory)")
            else:
                inventory_cents = round_cents(inventory_used * rate)
        paid = sum(item.cost_cents or 0 for item in items)
        bought = sum((item.bought or Decimal(0) for item in items), Decimal(0))
        remainder = sum((item.remainder or Decimal(0) for item in items), Decimal(0))
        left_cents = round_cents(remainder * Decimal(paid) / bought) if bought > 0 and remainder > 0 else 0
        used = paid - left_cents + inventory_cents
        eaten_cents = round_cents(Decimal(used) * share.get(ingredient_id, Decimal(1)))
        eaten += eaten_cents
        frozen += used - eaten_cents
        from_inventory += inventory_cents
        leftover += left_cents
        if remainder > 0 and significant(remainder, plan.planning_unit):
            fate = leftover_fate(plan, c)
            leftovers.append(
                LeftoverItem(ingredient_id, plan.name, plan.planning_unit, remainder, left_cents, fate)
            )
            if fate == "at_risk":
                waste += left_cents
    taken = {lot_id for lot_id, _ in grocery.inventory_takes}
    for plan in ingredients.values():
        rate = _inventory_rate(plan, c.store_ids)
        for lot in plan.lots:
            expiring = lot.expires_on is not None and lot.expires_on <= c.week_end
            frozen_lot = (lot.location or "fridge") == "freezer"
            if expiring and lot.id not in taken and rate is not None and not frozen_lot:
                waste += round_cents(lot.quantity * rate)
    summary = CostSummary(
        stock_up_cash_cents=grocery.stock_up_cents,
        cash_cents=grocery.total_cents,
        eaten_cents=eaten,
        from_inventory_cents=from_inventory,
        leftover_cents=leftover,
        frozen_portions_cents=frozen,
        expected_waste_cents=waste,
        complete=not unpriced,
        unpriced=tuple(unpriced),
    )
    return summary, tuple(leftovers)
