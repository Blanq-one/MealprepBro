"""Database → PlanningProblem: candidate recipes (seed drafts and saved versions), their exact per-portion
numbers, purchase offers at your stores, and inventory. Hard filters run here, and every recipe that is
left out keeps its reasons so the plan can say why.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InventoryItem, Product, Recipe, RecipeIngredient, RecipeVersion
from app.domain.cook_time import mood_allows
from app.domain.enums import Equipment, MealSlot, PlanningMode, RecipeMood
from app.domain.fridge_life import fridge_life
from app.domain.nutrition import CORE_CODES
from app.domain.purchase import Offer
from app.domain.units import BASE_UNIT_FOR_KIND, ConversionError, UnitKind, convert
from app.planning.problem import (
    CandidateRecipe,
    ExcludedRecipe,
    IngredientPlan,
    InventoryLot,
    PlanningProblem,
    RecipeLine,
)
from app.planning.recipe_math import cost_per_portion, need_per_portion, recipe_per_portion
from app.schemas.constraints import PlanConstraints
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.pricing import StorePrice, active_stores, current_prices

ACTIVE_ORIGINS = ("seed", "llm", "user")


def candidate_versions(session: Session, user_id: int) -> list[tuple[Recipe, RecipeVersion]]:
    """The default (latest) version of every live recipe: seed drafts, saved LLM recipes, your versions."""
    rows = session.execute(
        select(Recipe, RecipeVersion)
        .join(RecipeVersion, RecipeVersion.id == Recipe.default_version_id)
        .where(
            Recipe.user_id == user_id,
            Recipe.archived_at.is_(None),
            Recipe.origin.in_(ACTIVE_ORIGINS),
            RecipeVersion.status == "active",
        )
        .order_by(RecipeVersion.id)
    ).all()
    return [(r, v) for r, v in rows]


def version_lines(session: Session, version_ids: Iterable[int]) -> dict[int, list[RecipeLine]]:
    ids = list(version_ids)
    out: dict[int, list[RecipeLine]] = defaultdict(list)
    if not ids:
        return out
    for row in session.scalars(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_version_id.in_(ids))
        .order_by(RecipeIngredient.recipe_version_id, RecipeIngredient.position)
    ):
        out[row.recipe_version_id].append(
            RecipeLine(
                recipe_ingredient_id=row.id,
                ingredient_id=row.ingredient_id,
                quantity=row.quantity,
                unit=row.unit,
                authored_quantity=row.authored_quantity,
                authored_unit=row.authored_unit,
                optional=row.is_optional,
                role=row.role,
            )
        )
    return out


def _planning_unit(data: IngredientData, prices: list[StorePrice]) -> str:
    """The unit of the ingredient's price data when there is one, else its own base unit."""
    for p in sorted(prices, key=lambda p: (p.store_id, p.product_id)):
        return p.priced_unit
    return BASE_UNIT_FOR_KIND[UnitKind(data.units.default_unit_kind)].value


def _offers(
    data: IngredientData, unit: str, prices: list[StorePrice], products: Mapping[int, Product]
) -> tuple[Offer, ...]:
    offers = []
    for p in sorted(prices, key=lambda p: (p.store_id, p.product_id, p.observation_id)):
        product = products[p.product_id]
        try:
            cents_per_priced = Decimal(p.price_cents) / p.priced_quantity
            cents_per_unit = cents_per_priced * convert(Decimal(1), unit, p.priced_unit, data.units)
            if product.package_amount is None:
                offers.append(
                    Offer(
                        p.observation_id, p.product_id, p.store_id, None, None, cents_per_unit, p.is_estimate
                    )
                )
                continue
            package = convert(product.package_amount, product.package_unit, unit, data.units)
            package_in_priced = convert(
                product.package_amount, product.package_unit, p.priced_unit, data.units
            )
        except ConversionError:
            continue
        package_cents = int(
            (Decimal(p.price_cents) * package_in_priced / p.priced_quantity).quantize(
                Decimal(1), ROUND_HALF_UP
            )
        )
        offers.append(
            Offer(
                p.observation_id,
                p.product_id,
                p.store_id,
                package,
                package_cents,
                Decimal(package_cents) / package,
                p.is_estimate,
            )
        )
    return tuple(offers)


def load_ingredient_plans(
    session: Session, user_id: int, ingredient_ids: Iterable[int], store_ids: Iterable[int]
) -> dict[int, IngredientPlan]:
    """Ingredient data, offers at the given stores and active inventory lots, all in one planning unit per
    ingredient. Used by the problem loader and, separately, by the plan validator's own reload."""
    ids = sorted(set(ingredient_ids))
    data = load_ingredients(session, ids)
    allowed = set(store_ids)
    prices: dict[int, list[StorePrice]] = defaultdict(list)
    for p in current_prices(session, ids):
        if p.store_id in allowed:
            prices[p.ingredient_id].append(p)
    product_ids = {p.product_id for ps in prices.values() for p in ps}
    products = {p.id: p for p in session.scalars(select(Product).where(Product.id.in_(product_ids)))}
    lots: dict[int, list[InventoryItem]] = defaultdict(list)
    if ids:
        for item in session.scalars(
            select(InventoryItem)
            .where(
                InventoryItem.user_id == user_id,
                InventoryItem.ingredient_id.in_(ids),
                InventoryItem.status == "active",
                InventoryItem.quantity > 0,
            )
            .order_by(InventoryItem.id)
        ):
            lots[item.ingredient_id].append(item)
    plans: dict[int, IngredientPlan] = {}
    for i in ids:
        d = data[i]
        unit = _planning_unit(d, prices[i])
        inventory = []
        for item in lots[i]:
            try:
                quantity = convert(item.quantity, item.unit, unit, d.units)
            except ConversionError:
                continue
            inventory.append(
                InventoryLot(
                    item.id, i, quantity, item.opened_on, item.expires_on, item.acquired_on, item.location
                )
            )
        plans[i] = IngredientPlan(
            id=i,
            name=d.name,
            planning_unit=unit,
            units=d.units,
            profile=d.profile,
            count_rounding_step=d.count_rounding_step,
            staple=d.assume_in_stock,
            stock_up=d.stock_up,
            perishable=d.is_perishable,
            shelf_life_days_fridge=d.shelf_life_days_fridge,
            location=d.typical_location,
            fridge_life=fridge_life(d.slug, d.safety_category.value if d.safety_category else None),
            offers=_offers(d, unit, prices[i], products),
            lots=tuple(inventory),
        )
    return plans


def _cook_day_fits(c: PlanConstraints, mood: RecipeMood, active_minutes: int) -> bool:
    return any(
        d.is_cook_day and mood_allows(d.mood, mood) and active_minutes <= d.cook_minutes_available
        for d in c.days
    )


def build_problem(session: Session, user_id: int, constraints: PlanConstraints) -> PlanningProblem:
    c = constraints
    week_slots = {s for d in c.days for s in d.slots}
    pairs = candidate_versions(session, user_id)
    lines = version_lines(session, [v.id for _, v in pairs])
    ingredient_ids = {line.ingredient_id for ls in lines.values() for line in ls}
    plans = load_ingredient_plans(session, user_id, ingredient_ids, c.store_ids)
    data = load_ingredients(session, ingredient_ids)
    store_names = {s.id: s.name for s in active_stores(session) if s.id in c.store_ids}
    never_favored_ids = frozenset(
        i for cap in c.frequency_caps if cap.never_favor for i in cap.member_ingredient_ids
    )
    candidates: list[CandidateRecipe] = []
    excluded: list[ExcludedRecipe] = []
    for recipe, version in pairs:
        slots = frozenset(MealSlot(s) for s in version.meal_slots)
        if not slots & week_slots:
            continue  # nothing to fill this week; not an exclusion
        recipe_lines = lines.get(version.id, [])
        reasons: list[str] = []
        held: list[str] = []
        unpriced: list[str] = []
        for line in recipe_lines:
            if line.ingredient_id in c.excluded_ingredient_ids:
                name = data[line.ingredient_id].name
                if line.ingredient_id in c.held_ingredient_ids:
                    held.append(name)
                    reasons.append(f"held: {name} (possibly beef-derived; allow it in settings if it's fine)")
                else:
                    reasons.append(f"excluded: {name}")
        equipment = frozenset(Equipment(e) for e in version.equipment)
        if missing := sorted(equipment - c.equipment):
            reasons.append(f"needs equipment you don't have: {', '.join(missing)}")
        counted = [line for line in recipe_lines if not line.optional]
        for line in counted:
            profile = data[line.ingredient_id].profile
            if missing_core := [code for code in CORE_CODES if code not in profile.per_100g]:
                reasons.append(f"incomplete nutrition: {profile.name} has no {', '.join(missing_core)}")
        mood = RecipeMood(version.mood)
        if not _cook_day_fits(c, mood, version.active_minutes):
            reasons.append(
                f"needs {version.active_minutes} hands-on minutes on a {mood.value}-or-busier cook day; "
                "none of this week's cook days allows that"
            )
        for line in counted:
            plan = plans[line.ingredient_id]
            if plan.staple or plan.offers:
                continue
            if c.limit_covers(plan.stock_up) and plan.available <= 0:
                unpriced.append(plan.name)
        if unpriced:
            names = ", ".join(sorted(set(unpriced)))
            if c.planning_mode is PlanningMode.INVENTORY:
                why = (
                    f"unpriced: {names} isn't in your inventory and has no price at your stores, so a "
                    "top-up can't include it (add it to your inventory or enter a price)"
                )
            else:
                why = (
                    f"unpriced: {names} has no price at your stores, so your budget can't be checked "
                    "(enter a price, or plan without a budget)"
                )
            reasons.append(why)
        need: dict[int, Decimal] = {}
        if not reasons:
            try:
                need = need_per_portion(recipe_lines, plans, version.base_servings)
            except ConversionError as exc:
                reasons.append(f"can't convert a line to its purchase unit: {exc}")
        if reasons:
            excluded.append(
                ExcludedRecipe(
                    version.id,
                    version.title,
                    slots,
                    tuple(dict.fromkeys(reasons)),
                    tuple(held),
                    tuple(unpriced),
                )
            )
            continue
        totals = recipe_per_portion(recipe_lines, plans, version.base_servings)
        ids = {line.ingredient_id for line in recipe_lines}
        candidates.append(
            CandidateRecipe(
                version_id=version.id,
                recipe_id=recipe.id,
                title=version.title,
                meal_slots=slots,
                mood=mood,
                active_minutes=version.active_minutes,
                equipment=equipment,
                freezer_friendly=version.freezer_friendly,
                base_servings=version.base_servings,
                lines=tuple(recipe_lines),
                per_portion=totals.amounts,
                heme_iron_mg=totals.heme.heme_mg if totals.heme else Decimal(0),
                need_per_portion=need,
                cost_cents_per_portion=cost_per_portion(need, plans),
                total_minutes=version.total_minutes,
                origin=recipe.origin,
                is_draft=version.is_draft,
                never_favored=bool(ids & never_favored_ids),
                is_favorite=recipe.id in c.favorite_recipe_ids,
                has_disliked=bool(ids & c.disliked_ingredient_ids),
            )
        )
    return PlanningProblem(
        constraints=c,
        candidates=tuple(candidates),
        ingredients=plans,
        store_names=store_names,
        excluded=tuple(excluded),
    )
