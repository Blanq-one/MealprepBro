"""The grocery list from the rounded plan (deliverable 16).

need − inventory (open packages first, then earliest expiry) → exact package covers per (product, store) →
the store-split rule (R4): Stop & Shop unless buying some items at Price Rite saves ≥ the threshold this
week. Stock-up items (rice, oil, protein powder) are whole packages of the cheapest pack per unit, listed
apart. Staples (assume_in_stock) are listed as "check you have"; unknown prices are flagged, never guessed.
Money: each line is rounded once; totals are sums of lines (§7.1).
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

from app.domain.inventory_math import Lot, allocate
from app.domain.purchase import EMPTY_COVER_TOLERANCE, choose_stores
from app.planning.problem import IngredientPlan
from app.planning.rounded import GroceryItem, GroceryPlan, RoundedBatch
from app.schemas.constraints import PlanConstraints


def batch_needs(
    batches: Sequence[RoundedBatch], ingredients: Mapping[int, IngredientPlan]
) -> tuple[dict[int, Decimal], dict[int, list[str]]]:
    """Total need per ingredient (planning unit) over all non-optional rounded lines, and the recipes
    using it."""
    need: dict[int, Decimal] = defaultdict(Decimal)
    used_by: dict[int, list[str]] = defaultdict(list)
    for batch in batches:
        for line in batch.lines:
            if line.optional:
                continue
            plan = ingredients[line.ingredient_id]
            need[line.ingredient_id] += plan.to_planning(line.base_quantity, line.base_unit)
            if batch.title not in used_by[line.ingredient_id]:
                used_by[line.ingredient_id].append(batch.title)
    return dict(need), dict(used_by)


def build_grocery(
    constraints: PlanConstraints,
    batches: Sequence[RoundedBatch],
    ingredients: Mapping[int, IngredientPlan],
) -> GroceryPlan:
    need, used_by = batch_needs(batches, ingredients)
    items: list[GroceryItem] = []
    to_buy: dict[int, Decimal] = {}
    inventory_used: dict[int, Decimal] = {}
    takes: list[tuple[int, Decimal]] = []
    for ingredient_id in sorted(need):
        plan = ingredients[ingredient_id]
        if plan.staple:
            items.append(
                GroceryItem(
                    ingredient_id=ingredient_id,
                    name=plan.name,
                    unit=plan.planning_unit,
                    needed=need[ingredient_id],
                    inventory_used=Decimal(0),
                    to_buy=Decimal(0),
                    kind="staple",
                    recipes=tuple(used_by[ingredient_id]),
                    note="check you have",
                )
            )
            continue
        lots = [
            Lot(lot.id, lot.quantity, plan.planning_unit, lot.expires_on, lot.opened_on, lot.acquired_on)
            for lot in plan.lots
        ]
        allocation = allocate(need[ingredient_id], plan.planning_unit, lots, plan.units)
        takes.extend((t.lot_id, t.quantity) for t in allocation.takes)
        inventory_used[ingredient_id] = allocation.fulfilled
        to_buy[ingredient_id] = allocation.shortfall
    tolerance = {i: EMPTY_COVER_TOLERANCE.get(ingredients[i].planning_unit, Decimal(0)) for i in to_buy}
    choice = choose_stores(
        to_buy,
        {i: ingredients[i].offers for i in to_buy},
        constraints.primary_store_id,
        constraints.store_split_min_savings_cents,
        tolerance,
        stock_up_ids=frozenset(i for i in to_buy if ingredients[i].stock_up),
    )
    unpriced: list[str] = []
    for ingredient_id in sorted(to_buy):
        plan = ingredients[ingredient_id]
        base = GroceryItem(
            ingredient_id=ingredient_id,
            name=plan.name,
            unit=plan.planning_unit,
            needed=need[ingredient_id],
            inventory_used=inventory_used[ingredient_id],
            to_buy=to_buy[ingredient_id],
            kind="buy",
            perishable=plan.spoils_within(constraints.keep_horizon_days()),
            recipes=tuple(used_by[ingredient_id]),
            stock_up=plan.stock_up,
        )
        cover = choice.covers.get(ingredient_id)
        if to_buy[ingredient_id] <= tolerance[ingredient_id]:
            items.append(replace(base, kind="from_inventory", note="covered by what you have"))
            continue
        if cover is None:
            unpriced.append(plan.name)
            items.append(replace(base, kind="unpriced", note="no price at your stores yet"))
            continue
        forced = "only priced at another store" if ingredient_id in choice.forced_elsewhere else None
        for n, buy in enumerate(cover.buys):
            last = n == len(cover.buys) - 1
            items.append(
                replace(
                    base,
                    product_id=buy.offer.product_id,
                    store_id=buy.offer.store_id,
                    observation_id=buy.offer.ref,
                    packages=buy.packages,
                    bought=buy.quantity,
                    cost_cents=buy.cents,
                    is_estimate=buy.offer.is_estimate,
                    remainder=cover.remainder if last and cover.remainder > 0 else None,
                    note=forced,
                )
            )
    store_cents: dict[int, int] = defaultdict(int)
    for line in items:
        if line.cost_cents is not None and line.store_id is not None:
            store_cents[line.store_id] += line.cost_cents
    total = sum(store_cents.values())
    stock_up = sum(line.cost_cents or 0 for line in items if line.stock_up and line.store_id is not None)
    return GroceryPlan(
        items=tuple(items),
        store_cents=dict(store_cents),
        total_cents=total,
        complete=not unpriced,
        unpriced=tuple(unpriced),
        split=choice.split,
        primary_only_cents=choice.primary_only_cents,
        savings_cents=choice.savings_cents,
        forced_elsewhere=tuple(ingredients[i].name for i in choice.forced_elsewhere),
        inventory_takes=tuple(takes),
        stock_up_cents=stock_up,
    )
