"""Load canonical ingredients from the DB into the pure domain types (units, nutrition, tags)."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient, IngredientNutrient, IngredientUnit, Nutrient, UsdaFood
from app.domain.exclusions import TaggedIngredient
from app.domain.food_safety import SafetyCategory
from app.domain.food_state import FoodState, mapping_state
from app.domain.frequency_caps import CapIngredient
from app.domain.nutrition import NutritionProfile
from app.domain.units import IngredientUnits, UnitKind


@dataclass(frozen=True)
class IngredientData:
    id: int
    slug: str
    name: str
    category: str
    assume_in_stock: bool
    count_rounding_step: Decimal
    safety_category: SafetyCategory | None
    units: IngredientUnits
    profile: NutritionProfile
    tagged: TaggedIngredient
    nutrition_source: str
    fdc_id: int | None = None
    usda_description: str | None = None
    is_perishable: bool = False
    shelf_life_days_fridge: int | None = None
    shelf_life_days_pantry: int | None = None
    shelf_life_days_freezer: int | None = None
    typical_location: str | None = None
    stock_up: bool = False
    price_tier: str | None = None  # step 2b.6 (AA6): cheap | better | fancy; None = any tier

    @property
    def cap_view(self) -> CapIngredient:
        return CapIngredient(self.id, self.slug, self.tagged.diet_tags)

    @property
    def mapping_state(self) -> FoodState:
        """The state (raw / dry / cooked / as-sold) its nutrition describes."""
        return mapping_state(self.usda_description, self.category, self.nutrition_source)


def _build(
    ingredient: Ingredient,
    units: list[IngredientUnit],
    nutrients: dict[str, Decimal],
    usda_description: str | None,
) -> IngredientData:
    return IngredientData(
        id=ingredient.id,
        slug=ingredient.slug,
        name=ingredient.name,
        category=ingredient.category,
        assume_in_stock=ingredient.assume_in_stock,
        count_rounding_step=ingredient.count_rounding_step,
        safety_category=SafetyCategory(ingredient.safety_category) if ingredient.safety_category else None,
        units=IngredientUnits(
            name=ingredient.name,
            default_unit_kind=UnitKind(ingredient.default_unit_kind),
            density_g_per_ml=ingredient.density_g_per_ml,
            count_unit_weight_g=ingredient.count_unit_weight_g,
            named_units={u.unit_name: u.grams for u in units},
        ),
        profile=NutritionProfile(
            ingredient_id=ingredient.id,
            name=ingredient.name,
            per_100g=nutrients,
            heme_iron_fraction=ingredient.heme_iron_fraction,
            edible_fraction=ingredient.edible_fraction,
        ),
        tagged=TaggedIngredient(
            id=ingredient.id,
            name=ingredient.name,
            diet_tags=frozenset(ingredient.diet_tags or ()),
            review_note=ingredient.diet_review_note,
        ),
        nutrition_source=ingredient.nutrition_source,
        fdc_id=ingredient.fdc_id,
        usda_description=usda_description,
        is_perishable=ingredient.is_perishable,
        shelf_life_days_fridge=ingredient.shelf_life_days_fridge,
        shelf_life_days_pantry=ingredient.shelf_life_days_pantry,
        shelf_life_days_freezer=ingredient.shelf_life_days_freezer,
        typical_location=ingredient.typical_location,
        stock_up=ingredient.stock_up,
        price_tier=ingredient.price_tier,
    )


def load_ingredients(session: Session, ids: Iterable[int] | None = None) -> dict[int, IngredientData]:
    query = select(Ingredient)
    if ids is not None:
        id_list = list(set(ids))
        if not id_list:
            return {}
        query = query.where(Ingredient.id.in_(id_list))
    ingredients = list(session.scalars(query))
    wanted = [i.id for i in ingredients]
    units: dict[int, list[IngredientUnit]] = {i: [] for i in wanted}
    for unit in session.scalars(select(IngredientUnit).where(IngredientUnit.ingredient_id.in_(wanted))):
        units[unit.ingredient_id].append(unit)
    nutrients: dict[int, dict[str, Decimal]] = {i: {} for i in wanted}
    rows = session.execute(
        select(IngredientNutrient.ingredient_id, Nutrient.code, IngredientNutrient.amount_per_100g)
        .join(Nutrient, Nutrient.id == IngredientNutrient.nutrient_id)
        .where(IngredientNutrient.ingredient_id.in_(wanted))
    )
    for ingredient_id, code, amount in rows:
        nutrients[ingredient_id][code] = amount
    fdc_ids = {i.fdc_id for i in ingredients if i.fdc_id is not None}
    descriptions = dict(
        session.execute(select(UsdaFood.fdc_id, UsdaFood.description).where(UsdaFood.fdc_id.in_(fdc_ids)))
        .tuples()
        .all()
    )
    return {
        i.id: _build(i, units[i.id], nutrients[i.id], descriptions.get(i.fdc_id) if i.fdc_id else None)
        for i in ingredients
    }


def load_by_slug(session: Session) -> dict[str, IngredientData]:
    return {data.slug: data for data in load_ingredients(session).values()}


def nutrient_codes(session: Session) -> list[str]:
    return list(session.scalars(select(Nutrient.code).order_by(Nutrient.sort_order)))
