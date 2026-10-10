"""Pydantic models for the seed data files in app/seed/data/. They validate the JSON before anything is
written to the database."""

from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    Equipment,
    IngredientCategory,
    IngredientRole,
    InstructionSection,
    MealSlot,
    NutritionSource,
    PriceBasis,
    PriceSource,
    RecipeMood,
    StorageLocation,
)
from app.domain.exclusions import KNOWN_DIET_TAGS
from app.domain.food_safety import SafetyCategory
from app.domain.food_state import FoodState
from app.domain.quantities import parse_quantity
from app.domain.units import UnitKind


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------- nutrients ----------------
class SeedNutrient(_Strict):
    id: int = Field(ge=1, le=32767)
    code: str
    display_name: str
    unit: Literal["kcal", "g", "mg", "ug"]
    fdc_number: str
    usda_nutrient_ids: list[int] = Field(min_length=1)  # in order of preference
    is_core: bool
    daily_value: Decimal | None = None


class SeedNutrientFile(_Strict):
    schema_version: Literal[1]
    nutrients: list[SeedNutrient]


# ---------------- ingredients ----------------
class PortionRef(_Strict):
    usda_portion_id: int
    measure: Literal["tsp", "tbsp", "cup", "fl_oz"] | None = None  # required for densities


class LabelRef(_Strict):
    label: str  # key in label_inputs.json


class SeedUnit(_Strict):
    name: str
    usda_portion_id: int | None = None
    label: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.usda_portion_id is None) == (self.label is None):
            raise ValueError(f"unit '{self.name}': give exactly one of usda_portion_id or label")
        return self


class SeedShelfLife(_Strict):
    """How long a long-keeping item keeps where it usually lives (Phase 2): an estimate, with its basis."""

    pantry_days: int | None = Field(default=None, ge=1, le=3650)
    fridge_days: int | None = Field(default=None, ge=1, le=3650)
    freezer_days: int | None = Field(default=None, ge=1, le=3650)
    basis: str = Field(min_length=10)


class SeedIngredient(_Strict):
    name: str
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    category: IngredientCategory
    default_unit_kind: UnitKind
    nutrition_source: Literal[NutritionSource.USDA, NutritionSource.PACKAGE_LABEL]
    # A package-label ingredient may keep an fdc_id: label values override it, and USDA fills only the
    # nutrients the label doesn't list (each row records its own source).
    fdc_id: int | None
    aliases: list[str] = Field(default_factory=list)
    diet_tags: list[str] = Field(default_factory=list)
    diet_review_note: str | None = None
    heme_iron_fraction: Decimal = Field(ge=0, le=1)
    safety_category: SafetyCategory | None = None
    is_perishable: bool
    typical_location: StorageLocation
    shelf_life: SeedShelfLife | None = None  # unset = unknown (raw protein uses the FoodSafety.gov chart)
    assume_in_stock: bool = False
    stock_up: bool = False  # long-life, bought occasionally; listed apart from regular groceries
    count_rounding_step: Decimal = Field(default=Decimal(1), gt=0)
    density: PortionRef | None = None
    count_unit_weight: PortionRef | LabelRef | None = None
    units: list[SeedUnit] = Field(default_factory=list)
    notes: str | None = None
    nutrition_reviewed_on: date | None = None  # you approved this mapping (review sheet)

    @field_validator("diet_tags")
    @classmethod
    def _known_tags(cls, tags: list[str]) -> list[str]:
        if unknown := set(tags) - KNOWN_DIET_TAGS:
            raise ValueError(f"unknown diet tags: {sorted(unknown)}")
        return tags

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        if self.nutrition_source is NutritionSource.USDA and self.fdc_id is None:
            raise ValueError(f"{self.slug}: USDA-sourced ingredients need an fdc_id")
        if self.density is not None and self.density.measure is None:
            raise ValueError(f"{self.slug}: a density portion needs its measure (tsp/tbsp/cup/fl_oz)")
        if self.default_unit_kind is UnitKind.COUNT and self.count_unit_weight is None:
            raise ValueError(f"{self.slug}: count ingredients need a typical piece weight")
        if "possible_beef" in self.diet_tags and not self.diet_review_note:
            raise ValueError(f"{self.slug}: held (possible_beef) items need a review note")
        return self


class SeedIngredientFile(_Strict):
    schema_version: Literal[1]
    ingredients: list[SeedIngredient]


# ---------------- labels ----------------
class LabelNutrition(_Strict):
    serving_unit: str
    serving_grams: Decimal = Field(gt=0)
    per_serving: dict[str, Decimal | None]  # tracked nutrient codes; None = not filled in yet
    other_values: dict[str, Decimal] = Field(default_factory=dict)  # on the label, not tracked as nutrients
    allergens: list[str] = Field(default_factory=list)
    placeholders: list[str] = Field(default_factory=list)  # values still to be filled from the label
    source: Literal["package label"]
    note: str | None = None


class LabelPackage(_Strict):
    count: int = Field(gt=0)  # pieces or servings per package
    net_weight_g: Decimal = Field(gt=0)
    is_estimate: bool
    source: str


class LabelInputsFile(_Strict):
    schema_version: Literal[1]
    labels: dict[str, LabelNutrition] = Field(default_factory=dict)
    packages: dict[str, LabelPackage] = Field(default_factory=dict)


# ---------------- stores, products, prices ----------------
class SeedStore(_Strict):
    name: str
    priority: int = Field(ge=1)
    region_code: str | None = None
    kind: Literal["grocery", "other"] = "grocery"  # other: items your stores don't carry (never a trip)
    notes: str | None = None


class SeedStoreFile(_Strict):
    schema_version: Literal[1]
    stores: list[SeedStore]


class SeedAmount(_Strict):
    amount: Decimal = Field(gt=0)
    unit: str


class SeedPrice(_Strict):
    store: str
    price_cents: int = Field(ge=0)
    per: SeedAmount  # the quantity the price covers ($1.99 per 1 lb, $1.99 per 30 count)
    source: PriceSource
    note: str | None = None


class SeedProduct(_Strict):
    ingredient: str  # slug
    name: str
    brand: str | None = None
    store_brand_of: str | None = None  # store name when the product exists only at that store
    package: SeedAmount | None  # None = sold loose
    is_variable_weight: bool = False
    price_basis: PriceBasis
    display_unit: str
    is_default: bool = False
    prices: list[SeedPrice] = Field(default_factory=list)  # empty = price not known yet


class SeedProductFile(_Strict):
    schema_version: Literal[1]
    observed_on: str
    products: list[SeedProduct]


# ---------------- substitutions ----------------
class SeedSubstitution(_Strict):
    from_ingredient: str
    to_ingredient: str
    context_key: str = ""
    status: Literal["accepted"]
    quantity_rule: dict[str, str]
    culinary_note: str | None = None
    preparation_changes: str | None = None


class SeedSubstitutionFile(_Strict):
    schema_version: Literal[1]
    substitutions: list[SeedSubstitution]


# ---------------- recipes ----------------
_SECTION_EQUIPMENT = {
    InstructionSection.OVEN: Equipment.OVEN,
    InstructionSection.AIR_FRYER: Equipment.AIR_FRYER,
    InstructionSection.STOVETOP: Equipment.STOVETOP,
    InstructionSection.MICROWAVE: Equipment.MICROWAVE,
}


class SeedRecipeIngredient(_Strict):
    ingredient: str  # slug
    quantity: str
    unit: str
    preparation: str | None = None
    role: IngredientRole
    component: str | None = None
    optional: bool = False
    # Quantities are raw / dry / as-sold weights; set this only when a line is something else ("cooked").
    state: FoodState | None = None

    @field_validator("quantity")
    @classmethod
    def _parses(cls, value: str) -> str:
        parse_quantity(value)
        return value


class SeedRecipeStep(_Strict):
    section: InstructionSection
    text: str = Field(min_length=5, max_length=500)
    duration_minutes: int | None = Field(default=None, ge=0, le=720)
    appliance_temp_f: int | None = Field(default=None, ge=150, le=550)
    doneness_check_for: str | None = None  # ingredient slug; the app inserts the safe temperature


class SeedRecipe(_Strict):
    family: str
    title: str = Field(min_length=3, max_length=80)
    description: str = Field(max_length=300)
    meal_slots: list[MealSlot] = Field(min_length=1, max_length=3)
    mood: RecipeMood
    cuisine: str | None = None
    flavor_tags: list[str] = Field(default_factory=list, max_length=6)
    base_servings: int = Field(ge=1, le=12)
    active_minutes: int = Field(ge=1, le=240)
    total_minutes: int = Field(ge=1, le=720)
    equipment: list[Equipment] = Field(default_factory=list)
    freezer_friendly: bool
    ingredients: list[SeedRecipeIngredient] = Field(min_length=2, max_length=25)
    steps: list[SeedRecipeStep] = Field(min_length=3, max_length=30)
    draft_note: str

    @model_validator(mode="after")
    def _structure(self) -> Self:
        if self.total_minutes < self.active_minutes:
            raise ValueError("total_minutes must be >= active_minutes")
        slugs = [i.ingredient for i in self.ingredients]
        if len(set(slugs)) != len(slugs):
            raise ValueError("duplicate ingredient lines")
        sections = {s.section for s in self.steps}
        if InstructionSection.PREP not in sections or InstructionSection.PORTIONING not in sections:
            raise ValueError("include at least one PREP and one PORTIONING step")
        missing = {
            eq for sec, eq in _SECTION_EQUIPMENT.items() if sec in sections and eq not in self.equipment
        }
        if missing:
            raise ValueError(f"steps use equipment not listed: {sorted(missing)}")
        for sec in (InstructionSection.OVEN, InstructionSection.AIR_FRYER):
            sec_steps = [s for s in self.steps if s.section == sec]
            if sec_steps and all(s.appliance_temp_f is None for s in sec_steps):
                raise ValueError(f"{sec} steps must state an appliance temperature")
        for step in self.steps:
            if step.doneness_check_for is not None and step.doneness_check_for not in slugs:
                raise ValueError(
                    f"doneness check for '{step.doneness_check_for}', which is not an ingredient"
                )
        return self


# ---------------- pantry catalog (Phase 2b, step 2b.4: decisions J2, J4, J5) ----------------
class CulinaryGroup(_Strict):
    """Vegetables or herbs that can stand in for each other (J2). Swaps happen only inside a group."""

    key: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    members: list[str] = Field(min_length=1)  # ingredient slugs


class FoodForm(_Strict):
    form: Literal["fresh", "frozen", "canned", "dried"]
    label: str
    ingredient: str  # slug: each form is its own ingredient (nutrition and shelf life differ)


class Food(_Strict):
    """One food you can add in more than one form (J5)."""

    key: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    forms: list[FoodForm] = Field(min_length=2)


class VersionChoice(_Strict):
    key: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    ingredient: str | None  # None = "Not sure": the item stays the generic, held one
    nutrition_estimated: bool = False  # USDA has no exact entry for this version


class HeldVersions(_Strict):
    """A held item that comes in versions (J4): the question, the label guidance and the choices."""

    generic: str  # the held ingredient's slug
    question: str
    guidance: str
    choices: list[VersionChoice] = Field(min_length=2)

    @model_validator(mode="after")
    def _not_sure_last(self) -> Self:
        if [c.ingredient for c in self.choices].count(None) != 1 or self.choices[-1].ingredient is not None:
            raise ValueError(f"{self.generic}: exactly one 'Not sure' choice, and it comes last")
        return self


class PresetOption(_Strict):
    key: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str  # "16 oz bag"
    amount: Decimal = Field(gt=0)
    unit: str  # any unit the ingredient understands (oz, lb, fl_oz, count, can, clove, …)
    container: str | None = None  # "bag": the recipe page says "about half your bag" (J6)
    default: bool = False  # the most common size, used for "Not sure"


class IngredientPresets(_Strict):
    ingredient: str
    options: list[PresetOption] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_default(self) -> Self:
        if sum(1 for o in self.options if o.default) != 1:
            raise ValueError(f"{self.ingredient}: exactly one default preset")
        keys = [o.key for o in self.options]
        if len(set(keys)) != len(keys):
            raise ValueError(f"{self.ingredient}: duplicate preset keys")
        return self


class PantryCatalogFile(_Strict):
    """app/seed/data/pantry_catalog.json, written by scripts/build_pantry_catalog.py."""

    schema_version: Literal[1]
    presets_are_estimates: bool
    culinary_groups: list[CulinaryGroup]
    foods: list[Food]
    versions: list[HeldVersions]
    presets: list[IngredientPresets]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        grouped = [m for g in self.culinary_groups for m in g.members]
        if dupes := sorted({m for m in grouped if grouped.count(m) > 1}):
            raise ValueError(f"in more than one culinary group: {dupes}")
        formed = [f.ingredient for food in self.foods for f in food.forms]
        if dupes := sorted({m for m in formed if formed.count(m) > 1}):
            raise ValueError(f"a form of more than one food: {dupes}")
        preset = [p.ingredient for p in self.presets]
        if dupes := sorted({m for m in preset if preset.count(m) > 1}):
            raise ValueError(f"presets listed twice: {dupes}")
        return self
