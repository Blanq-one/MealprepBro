"""One-tap inventory adds (Phase 2, "minimal typing"): the ingredients your recipes use, each with its usual
package. Code picks the amount (a product's package size, or one piece of a count item); nothing is
guessed by the LLM."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Product, RecipeIngredient
from app.domain.enums import StorageLocation
from app.domain.exclusions import ExclusionStatus
from app.domain.units import UnitKind
from app.planning.loader import candidate_versions
from app.schemas.inventory import QuickPickOut
from app.services.exclusions import diet_status
from app.services.ingredient_data import load_ingredients
from app.services.plans import amount_display

CATEGORY_ORDER = ("protein", "dairy", "vegetable", "fruit", "grain", "legume", "nut_seed", "fat_oil")


def quick_picks(session: Session, user_id: int) -> list[QuickPickOut]:
    versions = [v.id for _, v in candidate_versions(session, user_id)]
    ids = set(
        session.scalars(
            select(RecipeIngredient.ingredient_id).where(RecipeIngredient.recipe_version_id.in_(versions))
        )
    )
    data = load_ingredients(session, ids)
    statuses = diet_status(session, user_id, data).results
    products: dict[int, Product] = {}
    for p in session.scalars(
        select(Product)
        .where(
            Product.ingredient_id.in_(ids), Product.archived_at.is_(None), Product.package_amount.is_not(None)
        )
        .order_by(Product.ingredient_id, Product.is_default.desc(), Product.id)
    ):
        products.setdefault(p.ingredient_id, p)
    picks: list[QuickPickOut] = []
    for i in sorted(ids):
        d = data[i]
        if d.assume_in_stock or statuses[i].status is not ExclusionStatus.ALLOWED:
            continue
        product = products.get(i)
        location = StorageLocation(d.typical_location or "fridge")
        if product is not None and product.package_amount is not None:
            size = amount_display(product.package_amount, product.package_unit)
            picks.append(
                QuickPickOut(
                    ingredient_id=i,
                    name=d.name,
                    category=d.category,
                    location=location,
                    quantity=product.package_amount,
                    unit=product.package_unit,
                    display=f"{product.name} ({size})",
                    product_id=product.id,
                )
            )
        elif d.units.default_unit_kind is UnitKind.COUNT:
            picks.append(
                QuickPickOut(
                    ingredient_id=i,
                    name=d.name,
                    category=d.category,
                    location=location,
                    quantity=1,
                    unit="count",
                    display="1",
                    product_id=None,
                )
            )
    rank = {c: n for n, c in enumerate(CATEGORY_ORDER)}
    return sorted(picks, key=lambda p: (rank.get(p.category, len(rank)), p.name))
