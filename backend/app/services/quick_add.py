"""One-tap inventory adds (Phase 2, "minimal typing"): the ingredients your recipes use, each with its usual
package. Code picks the amount (a product's package size, or one piece of a count item); nothing is
guessed by the LLM.

Phase 2b (P1 amount picker): each pick also offers Full, ¾, ½ and ¼ of that amount and the units a custom
amount can be typed in (domain/amount_options.py); a bulk add sends an option key or a custom amount, and
the server converts it."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Product, RecipeIngredient
from app.domain.amount_options import (
    AmountChoice,
    CustomUnit,
    OptionKey,
    amount_options,
    custom_units,
    noun,
    option_quantity,
)
from app.domain.enums import StorageLocation
from app.domain.exclusions import ExclusionStatus
from app.domain.units import BASE_UNIT_FOR_KIND, UnitError, UnitKind, normalize_unit
from app.planning.loader import candidate_versions
from app.schemas.inventory import AmountOptionOut, CustomUnitOut, QuickPickOut
from app.services.exclusions import diet_status
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.inventory import InventoryError
from app.services.plans import amount_display
from app.services.settings import load_settings

CATEGORY_ORDER = ("protein", "dairy", "vegetable", "fruit", "grain", "legume", "nut_seed", "fat_oil")


@dataclass(frozen=True)
class UsualAmount:
    quantity: Decimal  # base unit
    unit: str  # g | ml | count
    product: Product | None


def _usual(data: IngredientData, product: Product | None) -> UsualAmount | None:
    """A packaged product's package, else one piece of a count item; None = no usual amount."""
    if product is not None and product.package_amount is not None:
        return UsualAmount(product.package_amount, product.package_unit, product)
    if data.units.default_unit_kind is UnitKind.COUNT:
        return UsualAmount(Decimal(1), "count", None)
    return None


def _default_products(session: Session, ingredient_ids: set[int]) -> dict[int, Product]:
    products: dict[int, Product] = {}
    for p in session.scalars(
        select(Product)
        .where(
            Product.ingredient_id.in_(ingredient_ids),
            Product.archived_at.is_(None),
            Product.package_amount.is_not(None),
        )
        .order_by(Product.ingredient_id, Product.is_default.desc(), Product.id)
    ):
        products.setdefault(p.ingredient_id, p)
    return products


def _choices(
    data: IngredientData, usual: UsualAmount, us: bool
) -> tuple[tuple[AmountChoice, ...], tuple[CustomUnit, ...]]:
    piece = noun(data.name, dict(data.units.named_units))
    step = data.count_rounding_step
    options = amount_options(usual.quantity, usual.unit, piece, step, us)
    units = custom_units(usual.quantity, usual.unit, data.units, piece, count_step=step, us=us)
    return options, units


def quick_picks(session: Session, user_id: int) -> list[QuickPickOut]:
    versions = [v.id for _, v in candidate_versions(session, user_id)]
    ids = set(
        session.scalars(
            select(RecipeIngredient.ingredient_id).where(RecipeIngredient.recipe_version_id.in_(versions))
        )
    )
    data = load_ingredients(session, ids)
    statuses = diet_status(session, user_id, data).results
    products = _default_products(session, ids)
    us = load_settings(session, user_id).units == "us"
    picks: list[QuickPickOut] = []
    for i in sorted(ids):
        d = data[i]
        if d.assume_in_stock or statuses[i].status is not ExclusionStatus.ALLOWED:
            continue
        usual = _usual(d, products.get(i))
        if usual is None:
            continue
        options, units = _choices(d, usual, us)
        product = usual.product
        picks.append(
            QuickPickOut(
                ingredient_id=i,
                name=d.name,
                category=d.category,
                location=StorageLocation(d.typical_location or "fridge"),
                quantity=usual.quantity,
                unit=usual.unit,
                display=f"{product.name} ({amount_display(usual.quantity, usual.unit)})"
                if product is not None
                else "1",
                product_id=product.id if product is not None else None,
                amount_options=[
                    AmountOptionOut(key=o.key, quantity=o.quantity, unit=o.unit, display=o.display)
                    for o in options
                ],
                custom_units=[
                    CustomUnitOut(unit=u.unit, label=u.label, step=u.step, start=u.start) for u in units
                ],
            )
        )
    rank = {c: n for n, c in enumerate(CATEGORY_ORDER)}
    return sorted(picks, key=lambda p: (rank.get(p.category, len(rank)), p.name))


def resolve_amount(
    session: Session,
    user_id: int,
    ingredient_id: int,
    product_id: int | None,
    *,
    option: OptionKey | None = None,
    custom_amount: Decimal | None = None,
    custom_unit: str | None = None,
) -> tuple[Decimal, str]:
    """A bulk-add amount as (quantity, unit) for the inventory service: an option of the item's usual amount
    (the given product's package, else its usual product, else one piece), or a custom amount in one of the
    units the quick pick offers."""
    data = load_ingredients(session, [ingredient_id]).get(ingredient_id)
    if data is None:
        raise InventoryError(f"ingredient {ingredient_id} not found")
    product: Product | None = None
    if product_id is not None:
        product = session.get(Product, product_id)
        if product is None or product.ingredient_id != ingredient_id:
            raise InventoryError(f"product {product_id} is not a product of {data.name}")
    else:
        product = _default_products(session, {ingredient_id}).get(ingredient_id)
    usual = _usual(data, product)
    if option is not None:
        if usual is None:
            raise InventoryError(f"{data.name} has no usual package size: send an amount and a unit")
        return option_quantity(option, usual.quantity, usual.unit, data.count_rounding_step), usual.unit
    if custom_amount is None or custom_unit is None:
        raise InventoryError("send an amount option, or a custom amount with its unit")
    us = load_settings(session, user_id).units == "us"
    base = usual or UsualAmount(Decimal(1), BASE_UNIT_FOR_KIND[data.units.default_unit_kind].value, None)
    _, units = _choices(data, base, us)
    try:
        unit = normalize_unit(custom_unit, data.units.named_units)
    except UnitError as exc:
        raise InventoryError(f"{data.name}: {exc}") from exc
    allowed = [u.unit for u in units]
    if unit not in allowed:
        raise InventoryError(f"{data.name} can be added in {', '.join(allowed)}, not {custom_unit}")
    return custom_amount, unit
