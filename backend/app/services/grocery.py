"""The grocery list in the store (Phase 2): check items off, with the actual weight and price if you like,
then "Done shopping" turns what you bought into inventory lots and per-store price observations.

Both are safe to repeat. A check-off sets values, so replaying it changes nothing; "Done shopping" locks the
list, and a second call returns what the first one did. Each price observation carries a client_ref derived
from the list and the item, so it is stored exactly once.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    InventoryEvent,
    InventoryItem,
    MealPlan,
    PriceObservation,
)
from app.domain.enums import PriceSource, StorageLocation
from app.domain.expiry import ShelfLife, estimate_expiry
from app.domain.purchase import cheapest_cover
from app.domain.units import UnitError, convert, normalize_unit
from app.planning.loader import load_ingredient_plans
from app.services import products as product_service
from app.services.errors import ConflictError
from app.services.ingredient_data import load_ingredients
from app.services.inventory import LotInput, add_lot

Q3 = Decimal("0.001")
REF_NAMESPACE = uuid.UUID("6f1c4a52-3b1e-4d0a-9a55-6c4f6d1e2a01")  # fixed: refs must be reproducible


FROZEN_NOTE = "frozen on shopping day, as the plan said"


class GroceryError(ValueError):
    pass


def price_ref(list_id: int, item_id: int) -> uuid.UUID:
    """The client_ref of the price observation "Done shopping" writes for one item: the same every time."""
    return uuid.uuid5(REF_NAMESPACE, f"grocery-list:{list_id}:item:{item_id}")


def _item(session: Session, user_id: int, item_id: int) -> tuple[GroceryListItem, GroceryList]:
    item = session.get(GroceryListItem, item_id)
    glist = session.get(GroceryList, item.grocery_list_id) if item is not None else None
    if item is None or glist is None or glist.user_id != user_id:
        raise GroceryError(f"grocery item {item_id} not found")
    return item, glist


def check_off(session: Session, user_id: int, item_id: int, changes: dict[str, Any]) -> GroceryListItem:
    """Apply a check-off. `changes` holds only the fields the request sent: checked (bool), purchased_amount
    with purchased_unit (the weight or count you actually bought, in any unit), actual_price_cents (what the
    line cost). A field sent as null clears it."""
    item, glist = _item(session, user_id, item_id)
    if glist.status == "done":
        raise ConflictError("this trip is already done; check-offs can't change any more")
    if "checked" in changes:
        if changes["checked"]:
            item.checked_at = item.checked_at or datetime.now(UTC)  # a replay keeps the first time
        else:
            item.checked_at = None
    if "purchased_amount" in changes:
        amount = changes["purchased_amount"]
        if amount is None:
            item.purchased_quantity = None
        else:
            unit = changes.get("purchased_unit") or item.unit
            units = load_ingredients(session, [item.ingredient_id])[item.ingredient_id].units
            try:
                quantity = convert(Decimal(amount), normalize_unit(unit, units.named_units), item.unit, units)
            except (UnitError, ValueError) as exc:
                raise GroceryError(f"can't read {amount} {unit}: {exc}") from exc
            item.purchased_quantity = quantity.quantize(Q3)
    if "actual_price_cents" in changes:
        item.actual_price_cents = changes["actual_price_cents"]
    if glist.status == "open" and item.checked_at is not None:
        glist.status = "shopping"
    session.flush()
    return item


@dataclass
class CompleteResult:
    grocery_list: GroceryList
    lots: list[InventoryItem]
    prices_recorded: int
    already_done: bool
    skipped: list[str]


def _freeze_amounts(plan: MealPlan) -> dict[int, Decimal]:
    """Raw protein the plan says to freeze on shopping day, from this trip's purchase (planning units)."""
    out: dict[int, Decimal] = defaultdict(Decimal)
    for f in plan.totals.get("freeze", []):
        if f.get("source") == "purchase":
            out[int(f["ingredient_id"])] += Decimal(f["quantity"])
    return out


def _done_result(session: Session, glist: GroceryList) -> CompleteResult:
    item_ids = list(
        session.scalars(select(GroceryListItem.id).where(GroceryListItem.grocery_list_id == glist.id))
    )
    lot_ids = set(
        session.scalars(
            select(InventoryEvent.inventory_item_id).where(
                InventoryEvent.grocery_list_item_id.in_(item_ids), InventoryEvent.reason == "purchase"
            )
        )
    )
    lots = list(
        session.scalars(select(InventoryItem).where(InventoryItem.id.in_(lot_ids)).order_by(InventoryItem.id))
    )
    refs = [price_ref(glist.id, i) for i in item_ids]
    prices = len(
        list(session.scalars(select(PriceObservation.id).where(PriceObservation.client_ref.in_(refs))))
    )
    return CompleteResult(glist, lots, prices, True, [])


def complete(
    session: Session, user_id: int, list_id: int, purchased_on: date | None = None
) -> CompleteResult:
    """Done shopping: every checked item becomes an inventory lot (the weight you entered, else what the plan
    said to buy), split into a freezer lot when the plan says to freeze raw protein on shopping day; every
    checked item with an actual price becomes a price observation at its store."""
    glist = session.scalars(
        select(GroceryList).where(GroceryList.id == list_id).with_for_update()
    ).first()  # a second "Done shopping" waits here, then sees the list is done
    if glist is None or glist.user_id != user_id:
        raise GroceryError(f"grocery list {list_id} not found")
    if glist.status == "done":
        return _done_result(session, glist)
    plan = session.get(MealPlan, glist.meal_plan_id) if glist.meal_plan_id is not None else None
    day = purchased_on or datetime.now(UTC).date()
    items = list(
        session.scalars(
            select(GroceryListItem)
            .where(GroceryListItem.grocery_list_id == glist.id)
            .order_by(GroceryListItem.position)
        )
    )
    ingredients = {
        i.id: i
        for i in session.scalars(
            select(Ingredient).where(Ingredient.id.in_({it.ingredient_id for it in items}))
        )
    }
    freeze = _freeze_amounts(plan) if plan is not None else {}
    lots: list[InventoryItem] = []
    prices = 0
    skipped: list[str] = []
    for item in items:
        ingredient = ingredients[item.ingredient_id]
        if item.checked_at is None:
            if (item.reason or {}).get("kind") == "buy":
                skipped.append(ingredient.name)
            continue
        bought = item.purchased_quantity if item.purchased_quantity is not None else item.to_buy_quantity
        if bought <= 0:
            continue
        life = ShelfLife(
            ingredient.slug,
            ingredient.safety_category,
            ingredient.shelf_life_days_pantry,
            ingredient.shelf_life_days_fridge,
            ingredient.shelf_life_days_freezer,
        )
        to_freeze = min(freeze.pop(item.ingredient_id, Decimal(0)), bought)
        home = StorageLocation(ingredient.typical_location or "fridge")
        parts = [(StorageLocation.FREEZER, to_freeze), (home, bought - to_freeze)]
        for location, quantity in parts:
            if quantity <= 0:
                continue
            lots.append(
                add_lot(
                    session,
                    user_id,
                    LotInput(
                        ingredient_id=item.ingredient_id,
                        quantity=quantity.quantize(Q3),
                        unit=item.unit,
                        location=location,
                        product_id=item.product_id,
                        acquired_on=day,
                        expires_on=estimate_expiry(life, location.value, day),
                        expiry_is_estimate=True,
                        notes=FROZEN_NOTE if location is not home else None,
                        reason="purchase",
                        grocery_list_item_id=item.id,
                    ),
                )
            )
        if item.actual_price_cents is not None and item.product_id is not None and item.store_id is not None:
            product_service.add_price(
                session,
                product_id=item.product_id,
                store_id=item.store_id,
                price_cents=item.actual_price_cents,
                per_amount=bought,
                per_unit=item.unit,
                observed_on=day,
                source=PriceSource.IN_STORE,
                note=f"Done shopping, grocery list {glist.id}",
                client_ref=price_ref(glist.id, item.id),
            )
            prices += 1
    glist.status = "done"
    session.flush()
    return CompleteResult(glist, lots, prices, False, skipped)


# ---------------- step 2b.6: I'm out of this (AA5) ----------------
OUT_OF_IT_NOTE = "Added: you're out of it"


def add_item(
    session: Session,
    user_id: int,
    list_id: int,
    ingredient_id: int,
    *,
    quantity: Decimal,
    unit: str,
    store_ids: tuple[int, ...],
    recipe: str | None = None,
) -> tuple[GroceryListItem, bool]:
    """Put an ingredient on a shopping list (I'm out of this): the cheapest whole packages at your stores that
    cover `quantity`. Returns the item and whether it was added (False: it was already on the list to buy)."""
    glist = session.get(GroceryList, list_id)
    if glist is None or glist.user_id != user_id:
        raise GroceryError(f"grocery list {list_id} not found")
    if glist.status == "done":
        raise ConflictError("This trip is done, so it can't take more items; it goes on your next list.")
    items = list(session.scalars(select(GroceryListItem).where(GroceryListItem.grocery_list_id == glist.id)))
    for item in items:
        if (
            item.ingredient_id == ingredient_id
            and (item.is_manual or (item.reason or {}).get("kind") in ("buy", "unpriced"))
            and not item.checked_at
        ):
            return item, False
    plan = load_ingredient_plans(session, user_id, [ingredient_id], store_ids)[ingredient_id]
    try:
        need = plan.to_planning(quantity, unit).quantize(Q3)
    except UnitError as exc:
        raise GroceryError(f"can't read {quantity} {unit}: {exc}") from exc
    cover = cheapest_cover(need, plan.offers)
    buys = cover.buys if cover is not None else ()
    first = buys[0] if buys else None
    packages = sum(b.packages or 0 for b in buys) or None
    item = GroceryListItem(
        grocery_list_id=glist.id,
        position=max((i.position for i in items), default=0) + 1,
        ingredient_id=ingredient_id,
        product_id=first.offer.product_id if first else None,
        store_id=first.offer.store_id if first else None,
        needed_quantity=need,
        inventory_used_quantity=Decimal(0),
        to_buy_quantity=(cover.purchased if cover is not None else need).quantize(Q3),
        expected_remainder_quantity=cover.remainder.quantize(Q3)
        if cover is not None and cover.remainder
        else None,
        unit=plan.planning_unit,
        packages=packages,
        estimated_cost_cents=cover.cents if cover is not None else None,
        price_observation_id=first.offer.ref if first else None,
        is_manual=True,
        reason={
            "kind": "buy" if cover is not None else "unpriced",
            "recipes": [recipe] if recipe else [],
            "note": OUT_OF_IT_NOTE,
            "is_estimate": any(b.offer.is_estimate for b in buys),
            "perishable": plan.perishable,
            "stock_up": plan.stock_up,
            "to_buy_total": str(need),
        },
    )
    session.add(item)
    session.flush()
    return item, True
