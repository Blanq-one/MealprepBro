"""API request/response models (Phase 0 endpoints). The frontend does no math: numbers come pre-computed,
with display strings where formatting matters."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import PortionSize
from app.domain.quantities import parse_quantity


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthOut(_Out):
    status: str
    database: str


class IngredientSearchHitOut(_Out):
    id: int
    name: str
    slug: str
    category: str
    matched_alias: str
    score: float
    status: str  # allowed | excluded | held
    reasons: list[str]
    frequency_caps: list[str]


class NutrientPer100gOut(_Out):
    code: str
    display_name: str
    unit: str
    amount_per_100g: Decimal
    source: str


class UnitOut(_Out):
    name: str
    grams: Decimal
    source: str


class PriceOut(_Out):
    store_id: int
    store_name: str
    product_id: int
    product_name: str
    price_cents: int
    priced_quantity: Decimal
    priced_unit: str
    observed_on: str
    is_estimate: bool


class IngredientDetailOut(_Out):
    id: int
    name: str
    slug: str
    category: str
    default_unit_kind: str
    density_g_per_ml: Decimal | None
    count_unit_weight_g: Decimal | None
    diet_tags: list[str]
    status: str
    reasons: list[str]
    frequency_caps: list[str]
    heme_iron_fraction: Decimal
    safety_category: str | None
    assume_in_stock: bool
    nutrition_source: str
    fdc_id: int | None
    notes: str | None
    aliases: list[str]
    nutrients: list[NutrientPer100gOut]
    units: list[UnitOut]
    prices: list[PriceOut]


class RecipeLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingredient_id: int
    quantity: str | Decimal = Field(description="Number or fraction, e.g. '1 1/4'")
    unit: str
    optional: bool = False

    @field_validator("quantity")
    @classmethod
    def _parse(cls, value: str | Decimal) -> Decimal:
        return parse_quantity(value)


class RecipeCalculationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    servings: int = Field(ge=1, le=50, description="Portions the lines make as written")
    lines: list[RecipeLineIn] = Field(min_length=1, max_length=60)
    scale_to_portions: int | None = Field(default=None, ge=1, le=50)
    portion_size: PortionSize = PortionSize.NORMAL


class NutrientAmountOut(_Out):
    code: str
    display_name: str
    unit: str
    amount: Decimal
    complete: bool
    missing_from: list[str]
    label: str | None = None  # 'good_source' | 'high_in' (per portion, code-generated)


class HemeOut(_Out):
    heme_mg: Decimal
    non_heme_mg: Decimal
    label: str = "estimated"


class NutritionOut(_Out):
    kcal: int
    nutrients: list[NutrientAmountOut]
    heme_iron: HemeOut | None


class StoreCostOut(_Out):
    store_id: int
    store_name: str
    total_cents: int
    per_portion_cents: int
    complete: bool
    unpriced: list[str]
    staples_not_costed: list[str]
    uses_estimates: bool


class CalculatedLineOut(_Out):
    ingredient_id: int
    name: str
    quantity: Decimal
    unit: str
    display: str
    optional: bool


class RecipeCalculationOut(_Out):
    portions: int
    scale_factor: Decimal
    lines: list[CalculatedLineOut]
    total: NutritionOut
    per_portion: NutritionOut
    costs: list[StoreCostOut]
    optional_not_counted: list[str]
    nutrition_complete: bool
    incomplete_reasons: list[str]


class SeedRecipeOut(_Out):
    recipe_id: int
    version_id: int
    family: str | None
    title: str
    is_draft: bool
    draft_note: str | None
    meal_slots: list[str]
    mood: str
    base_servings: int
    active_minutes: int
    total_minutes: int
    equipment: list[str]
    status: str  # complete | incomplete
    incomplete_reasons: list[str]
    per_serving: NutritionOut
    costs: list[StoreCostOut]
