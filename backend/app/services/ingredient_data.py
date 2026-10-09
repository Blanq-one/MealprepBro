"""Load canonical ingredients from the DB into the pure domain types (units, nutrition, tags)."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient, IngredientNutrient, IngredientUnit, Nutrient
from app.domain.exclusions import TaggedIngredient
from app.domain.food_safety import SafetyCategory
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

    @property
    def cap_view(self) -> CapIngredient:
        return CapIngredient(self.id, self.slug, self.tagged.diet_tags)


def _build(
    ingredient: Ingredient, units: list[IngredientUnit], nutrients: dict[str, Decimal]
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
    return {i.id: _build(i, units[i.id], nutrients[i.id]) for i in ingredients}


def load_by_slug(session: Session) -> dict[str, IngredientData]:
    return {data.slug: data for data in load_ingredients(session).values()}


def nutrient_codes(session: Session) -> list[str]:
    return list(session.scalars(select(Nutrient.code).order_by(Nutrient.sort_order)))
