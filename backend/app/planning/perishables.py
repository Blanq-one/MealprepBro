"""What happens to perishable food after the plan (item 3 of the Phase 1 fix-up):

* Raw meat, poultry and fish that won't be cooked within its fridge life of shopping day (the short end of
  the FoodSafety.gov chart's range) gets a "freeze on shopping day" instruction: the part for a later cook
  day (thaw it in the fridge the night before) and whatever is left of the package. Inventory lots of raw
  protein in the fridge get the same treatment against their own dates.
* Leftovers from this trip carry into your inventory. Each gets a fate: freeze (raw protein), keeps
  (pantry, freezer, non-perishable, or a chart fridge life that outlasts next week), or at_risk
  (perishable with no planned use; this is the expected waste).

Assumes you shop on the plan's first day and that inventory covers the earliest uses (it is allocated
before purchases, open packages first). Pure functions of the rounded batches and the grocery plan.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.domain.inventory_math import Lot, consumption_order
from app.planning.problem import IngredientPlan, InventoryLot
from app.planning.rounded import FreezeInstruction, GroceryPlan, RoundedBatch
from app.schemas.constraints import PlanConstraints

MIN_REMAINDER = {"g": Decimal(5), "ml": Decimal(5), "count": Decimal("0.5")}
KEEPS_LOCATIONS = frozenset({"pantry", "freezer"})


@dataclass(frozen=True)
class Use:
    day: date
    quantity: Decimal  # planning units
    recipe: str


def uses_by_ingredient(
    batches: Sequence[RoundedBatch], ingredients: Mapping[int, IngredientPlan]
) -> dict[int, list[Use]]:
    """Each batch's need for each ingredient on its cook day, earliest first."""
    out: dict[int, list[Use]] = defaultdict(list)
    for batch in batches:
        need: dict[int, Decimal] = defaultdict(Decimal)
        for line in batch.lines:
            if not line.optional:
                plan = ingredients[line.ingredient_id]
                need[line.ingredient_id] += plan.to_planning(line.base_quantity, line.base_unit)
        for ingredient_id, quantity in need.items():
            out[ingredient_id].append(Use(batch.cook_on, quantity, batch.title))
    for uses in out.values():
        uses.sort(key=lambda u: (u.day, u.recipe))
    return dict(out)


def significant(quantity: Decimal, unit: str) -> bool:
    return quantity >= MIN_REMAINDER.get(unit, Decimal(1))


def leftover_fate(plan: IngredientPlan, c: PlanConstraints) -> str:
    """freeze | keeps | at_risk, for what's left of this trip's purchase at the end of the week."""
    if plan.fridge_life is not None and plan.fridge_life.freeze_raw:
        return "freeze"
    if not plan.perishable or (plan.location or "fridge") in KEEPS_LOCATIONS:
        return "keeps"
    days = plan.fridge_life.days if plan.fridge_life is not None else plan.shelf_life_days()
    # it keeps if it would still be good at the end of next week's plan
    if days is not None and days >= c.keep_horizon_days():
        return "keeps"
    return "at_risk"


def _lot_safe_until(lot: InventoryLot, fridge_days: int) -> date | None:
    if lot.expires_on is not None:
        return lot.expires_on
    start = lot.opened_on or lot.acquired_on
    return start + timedelta(days=fridge_days) if start is not None else None


def _consume(uses: list[Use], amount: Decimal) -> tuple[list[Use], list[Use]]:
    """Split the earliest uses off, up to `amount`: (covered, remaining)."""
    covered: list[Use] = []
    remaining: list[Use] = []
    left = amount
    for use in uses:
        if left <= 0:
            remaining.append(use)
        elif use.quantity <= left:
            covered.append(use)
            left -= use.quantity
        else:
            covered.append(Use(use.day, left, use.recipe))
            remaining.append(Use(use.day, use.quantity - left, use.recipe))
            left = Decimal(0)
    return covered, remaining


def _day(d: date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def freeze_text(f: FreezeInstruction, amount: str) -> str:
    """One line of the plan, e.g. 'Freeze 600 g chicken thigh on shopping day (Mon Oct 12) for Everyday
    chicken curry gravy on Thu Oct 15; thaw it in the fridge Wed night (...)'."""
    days = f"{f.fridge_days} day" + ("" if f.fridge_days == 1 else "s")
    raw = f"raw, it keeps {days} in the fridge per FoodSafety.gov"
    where = "from your inventory " if f.source == "inventory" else ""
    if f.use_on is None or f.thaw_on is None:
        return (
            f"Freeze {amount} {f.name} {where}on shopping day ({_day(f.freeze_on)}): no use planned this "
            f"week, so it carries into your inventory, frozen ({raw})."
        )
    return (
        f"Freeze {amount} {f.name} {where}on shopping day ({_day(f.freeze_on)}) for {f.recipe} on "
        f"{_day(f.use_on)}; thaw it in the fridge {f.thaw_on:%a} night ({raw})."
    )


def _instruction(
    plan: IngredientPlan, freeze_on: date, quantity: Decimal, source: str, use: Use | None
) -> FreezeInstruction:
    assert plan.fridge_life is not None
    return FreezeInstruction(
        ingredient_id=plan.id,
        name=plan.name,
        unit=plan.planning_unit,
        quantity=quantity,
        freeze_on=freeze_on,
        fridge_days=plan.fridge_life.days,
        source=source,
        use_on=use.day if use is not None else None,
        recipe=use.recipe if use is not None else None,
    )


def _ingredient_freezes(
    c: PlanConstraints,
    plan: IngredientPlan,
    uses: list[Use],
    taken: Mapping[int, Decimal],
    purchased: Decimal,
) -> list[FreezeInstruction]:
    assert plan.fridge_life is not None
    shop = c.shopping_day
    unit = plan.planning_unit
    out: list[FreezeInstruction] = []
    remaining = list(uses)
    # inventory first, open packages first (the grocery list's order)
    lots = {lot.id: lot for lot in plan.lots}
    order = consumption_order(
        [Lot(lot.id, lot.quantity, unit, lot.expires_on, lot.opened_on, lot.acquired_on) for lot in plan.lots]
    )
    for ordered in order:
        lot = lots[ordered.id]
        used = taken.get(lot.id, Decimal(0))
        covered, remaining = _consume(remaining, used)
        if (lot.location or "fridge") == "freezer":
            continue
        safe_until = _lot_safe_until(lot, plan.fridge_life.days)
        if safe_until is None or safe_until < shop:
            continue  # no date, or past it already: the plan's EXPIRING warnings cover it
        for use in covered:
            if use.day > safe_until and significant(use.quantity, unit):
                out.append(_instruction(plan, shop, use.quantity, "inventory", use))
        unused = lot.quantity - used
        if safe_until <= c.week_end and significant(unused, unit):
            out.append(_instruction(plan, shop, unused, "inventory", None))
    if purchased <= 0:
        return out
    safe_until = shop + timedelta(days=plan.fridge_life.days)
    covered, _ = _consume(remaining, purchased)
    for use in covered:
        if use.day > safe_until and significant(use.quantity, unit):
            out.append(_instruction(plan, shop, use.quantity, "purchase", use))
    left = purchased - sum((u.quantity for u in covered), Decimal(0))
    if significant(left, unit):
        out.append(_instruction(plan, shop, left, "purchase", None))
    return out


def freeze_instructions(
    c: PlanConstraints,
    batches: Sequence[RoundedBatch],
    grocery: GroceryPlan,
    ingredients: Mapping[int, IngredientPlan],
) -> tuple[FreezeInstruction, ...]:
    uses = uses_by_ingredient(batches, ingredients)
    taken: dict[int, Decimal] = defaultdict(Decimal)
    for lot_id, quantity in grocery.inventory_takes:
        taken[lot_id] += quantity
    bought: dict[int, Decimal] = defaultdict(Decimal)
    for item in grocery.items:
        if item.kind == "buy" and item.bought is not None:
            bought[item.ingredient_id] += item.bought
    out: list[FreezeInstruction] = []
    for ingredient_id, plan in sorted(ingredients.items()):
        if plan.fridge_life is None or not plan.fridge_life.freeze_raw or plan.staple:
            continue
        out += _ingredient_freezes(
            c, plan, uses.get(ingredient_id, []), taken, bought.get(ingredient_id, Decimal(0))
        )
    return tuple(out)
