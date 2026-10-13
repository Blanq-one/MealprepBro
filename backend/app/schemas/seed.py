"""Pydantic models for the seed data files in app/seed/data/. They validate the JSON before anything is
written to the database."""

from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.cook_schedule import MAX_HANDS_ON, MAX_WAIT, OFF_DAY_SECTIONS, step_timing_errors
from app.domain.enums import (
    Equipment,
    IngredientCategory,
    IngredientRole,
    InstructionSection,
    MealSlot,
    NutritionSource,
    PairStyle,
    PrepState,
    PriceBasis,
    PriceSource,
    RecipeMood,
    StorageLocation,
)
from app.domain.exclusions import KNOWN_DIET_TAGS
from app.domain.food_safety import SafetyCategory
from app.domain.food_state import FoodState
from app.domain.price_tiers import IngredientTier, TierBasis
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


class SeedRefuse(_Strict):
    """The inedible share of an ingredient as purchased (bone, decision M5), from USDA SR28 FOOD_DES
    "Refuse". A package's weight times (1 - pct/100) is its edible weight for nutrition and portions."""

    pct: Decimal = Field(gt=0, lt=100)
    description: str = Field(min_length=3)  # "bone", "bone and cartilage"
    source: str = Field(min_length=10)  # the SR28 record and value it comes from


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
    # step 2b.6 (AA6): its budget tier (none = any tier: seasonings, oils, condiments) and what it rests on
    price_tier: IngredientTier | None = None
    price_tier_basis: TierBasis | None = None
    count_rounding_step: Decimal = Field(default=Decimal(1), gt=0)
    density: PortionRef | None = None
    count_unit_weight: PortionRef | LabelRef | None = None
    units: list[SeedUnit] = Field(default_factory=list)
    refuse: SeedRefuse | None = None  # bone-in cuts (M5): unset = all of it is edible
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
        if (self.price_tier is None) != (self.price_tier_basis is None):
            raise ValueError(f"{self.slug}: a price tier needs its basis (and a basis its tier)")
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


class SeedBudgetLine(_Strict):
    """A budget equivalent of a line's (classic) ingredient, with its own amount (2b.6 approval, item 4):
    canned diced tomatoes for fresh ones in a curry. Same culinary role: the same ingredient category, never a
    protein (chicken forms stay exact)."""

    ingredient: str  # slug
    quantity: str
    unit: str

    @field_validator("quantity")
    @classmethod
    def _parses(cls, value: str) -> str:
        parse_quantity(value)
        return value


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
    budget: SeedBudgetLine | None = None  # a budget equivalent (2b.6 approval, item 4)

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
    # step timing, tagged by hand on every seed step (step 2b.9, FLOW_SPEC §20.1): the part of the dish it
    # works on (unset = shared: prep for everything, assembly, portioning), the appliance it occupies (unset =
    # hands only, or waiting), its hands-on and hands-off minutes. Storage and reheating steps are 0 and 0.
    component: str | None = Field(default=None, min_length=1, max_length=30)
    equipment: Equipment | None = None
    hands_on_minutes: int = Field(ge=0, le=MAX_HANDS_ON)
    hands_off_minutes: int = Field(ge=0, le=MAX_WAIT)


SEED_HANDS_ON_TOLERANCE = 5  # a seed's tagged hands-on total vs its stated active minutes (2b.9 AC 2)


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
    # how to freeze it, when that needs saying (step 2b.5, H5): "Freeze the chicken and rice; make the yogurt
    # sauce and salad fresh"
    freeze_note: str | None = Field(default=None, min_length=5, max_length=200)

    @model_validator(mode="after")
    def _structure(self) -> Self:
        if self.total_minutes < self.active_minutes:
            raise ValueError("total_minutes must be >= active_minutes")
        if self.freeze_note is not None and not self.freezer_friendly:
            raise ValueError("a freeze note needs freezer_friendly: true")
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
        equipment = [e.value for e in self.equipment]
        for n, step in enumerate(self.steps, start=1):
            errors = step_timing_errors(
                step.section.value,
                step.equipment.value if step.equipment else None,
                step.hands_on_minutes,
                step.hands_off_minutes,
                equipment,
            )
            if step.section.value in OFF_DAY_SECTIONS and (step.hands_on_minutes or step.hands_off_minutes):
                errors.append("storage and reheating steps take 0 and 0 minutes (not cook-day work)")
            if errors:
                raise ValueError(f"step {n}: {'; '.join(errors)}")
        hands_on = sum(s.hands_on_minutes for s in self.steps)
        if abs(hands_on - self.active_minutes) > SEED_HANDS_ON_TOLERANCE:
            raise ValueError(
                f"the steps' hands-on minutes add up to {hands_on}, more than {SEED_HANDS_ON_TOLERANCE} from "
                f"active_minutes ({self.active_minutes}); revise one of them"
            )
        return self


# ---------------- smart prep (step 2b.10, FLOW_SPEC §19.6) ----------------
STATE_ORDER = list(PrepState)


class SeedPrepStage(_Strict):
    state: PrepState


class SeedPrepStep(SeedRecipeStep):
    stage: int = Field(ge=1, le=3)  # the stage the step belongs to


class SeedPrepItem(SeedRecipe):
    """A draft prep item split from a seed dish along its ingredient components: its steps grouped into stages
    (prep can stop after any stage its storage allows), a short label for meal names, the styles it pairs
    with. Its family is the seed's family and its draft note names the seed."""

    split_from: str = Field(pattern=r"^\d+[a-z]$")  # the seed it came from: "1a"
    label: str = Field(min_length=3, max_length=30)
    pairs_with: list[PairStyle] = Field(min_length=1, max_length=3)
    stages: list[SeedPrepStage] = Field(min_length=1, max_length=3)
    steps: list[SeedPrepStep] = Field(min_length=3, max_length=30)  # type: ignore[assignment]

    @model_validator(mode="after")
    def _stages(self) -> Self:
        order = [STATE_ORDER.index(s.state) for s in self.stages]
        if order != sorted(set(order)):
            raise ValueError("stages go in order, each a later state: raw, marinated, partly cooked, cooked")
        last = len(self.stages)
        stages = [step.stage for step in self.steps]
        if any(n > last for n in stages):
            raise ValueError(f"a step names stage {max(stages)}, but the item has {last}")
        if stages != sorted(stages):
            raise ValueError("steps go stage by stage")
        if missing := sorted(set(range(1, last + 1)) - set(stages)):
            raise ValueError(f"stage {missing[0]} has no steps")
        for step in self.steps:
            if step.section in (InstructionSection.PORTIONING, *OFF_DAY_SECTIONS) and step.stage != last:
                raise ValueError(f"{step.section} steps belong to the last stage")
        if self.split_from not in self.draft_note:
            raise ValueError(f"the draft note names the seed it came from ({self.split_from})")
        return self


class SeedAssemblyItem(_Strict):
    item: str  # a seed prep item's or dish's title
    portions: Decimal = Field(gt=0, le=4)  # usual portions per person
    min_portions: Decimal = Field(gt=0, le=4)
    max_portions: Decimal = Field(gt=0, le=4)
    step: Literal["0.5", "1"]

    @model_validator(mode="after")
    def _range(self) -> Self:
        step = Decimal(self.step)
        if not self.min_portions <= self.portions <= self.max_portions:
            raise ValueError(f"{self.item}: portions go from min_portions to max_portions")
        if any(v % step for v in (self.portions, self.min_portions, self.max_portions)):
            raise ValueError(f"{self.item}: portions are whole steps of {self.step}")
        return self


class SeedAssembly(_Strict):
    """A draft assembly: a meal built from prep items plus fresh add-ons (per portion). Code names it when it
    has no title, and composes its eating-day instruction."""

    title: str | None = Field(default=None, min_length=3, max_length=80)
    family: str | None = None
    meal_slots: list[MealSlot] = Field(min_length=1, max_length=3)
    items: list[SeedAssemblyItem] = Field(min_length=1, max_length=3)
    add_ons: list[SeedRecipeIngredient] = Field(default_factory=list, max_length=4)
    draft_note: str

    @model_validator(mode="after")
    def _unique(self) -> Self:
        names = [i.item for i in self.items]
        if len(set(names)) != len(names):
            raise ValueError("an item listed twice")
        slugs = [a.ingredient for a in self.add_ons]
        if len(set(slugs)) != len(slugs):
            raise ValueError("duplicate add-ons")
        return self


# ---------------- pantry catalog (Phase 2b, step 2b.4: decisions J2, J4, J5) ----------------
class CulinaryGroup(_Strict):
    """Vegetables or herbs that can stand in for each other (J2). Swaps happen only inside a group."""

    key: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    members: list[str] = Field(min_length=1)  # ingredient slugs


class FoodForm(_Strict):
    # fresh, frozen, canned, dried (J5); a chicken cut's bone and skin (M4)
    form: Literal["fresh", "frozen", "canned", "dried", "boneless_skinless", "bone_in_skin_on"]
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


class ChickenCut(_Strict):
    """A chicken cut's bone and skin (M6): exact, never swapped for another form in search, the resolver or a
    substitute."""

    ingredient: str
    bone: Literal["bone_in", "boneless"]
    skin: Literal["skin_on", "skinless"]


class CloseMatch(_Strict):
    """A name with no ingredient of its own, mapped to the closest one and always labeled (M7): "canned peas"
    → "Closest match: peas, frozen"."""

    alias: str = Field(min_length=2)
    ingredient: str


class MeatFormEntry(_Strict):
    """Ground meat, a whole cut, a fish fillet or shellfish (2b.4 fixes approval, N2; 2b.3b approval, P2):
    each swaps only within its group, and a whole cut only with one of the same bone and skin."""

    ingredient: str
    kind: Literal["ground", "whole_cut", "fish_fillet", "shellfish"]
    bone: Literal["bone_in", "boneless"] | None = None  # whole cuts only
    skin: Literal["skin_on", "skinless"] | None = None

    @model_validator(mode="after")
    def _form(self) -> Self:
        has_form = self.bone is not None or self.skin is not None
        if self.kind != "whole_cut" and has_form:
            raise ValueError(f"{self.ingredient}: only a whole cut has a bone and skin form")
        if self.kind == "whole_cut" and (self.bone is None or self.skin is None):
            raise ValueError(f"{self.ingredient}: a whole cut needs its bone and skin")
        return self


class PantryCatalogFile(_Strict):
    """app/seed/data/pantry_catalog.json, written by scripts/build_pantry_catalog.py."""

    schema_version: Literal[1]
    presets_are_estimates: bool
    culinary_groups: list[CulinaryGroup]
    foods: list[Food]
    versions: list[HeldVersions]
    presets: list[IngredientPresets]
    chicken_cuts: list[ChickenCut] = Field(default_factory=list)
    close_matches: list[CloseMatch] = Field(default_factory=list)
    meat_forms: list[MeatFormEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _meat_forms(self) -> Self:
        meats = [m.ingredient for m in self.meat_forms]
        if dupes := sorted({m for m in meats if meats.count(m) > 1}):
            raise ValueError(f"meat forms listed twice: {dupes}")
        forms = {m.ingredient: m for m in self.meat_forms}
        for cut in self.chicken_cuts:  # every chicken cut is a whole cut of its own bone and skin
            entry = forms.get(cut.ingredient)
            if entry is None or (entry.kind, entry.bone, entry.skin) != ("whole_cut", cut.bone, cut.skin):
                raise ValueError(
                    f"{cut.ingredient}: list it in meat_forms as a whole cut, {cut.bone} {cut.skin}"
                )
        return self

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
        cuts = [c.ingredient for c in self.chicken_cuts]
        if dupes := sorted({m for m in cuts if cuts.count(m) > 1}):
            raise ValueError(f"chicken cuts listed twice: {dupes}")
        close = [c.alias for c in self.close_matches]
        if dupes := sorted({m for m in close if close.count(m) > 1}):
            raise ValueError(f"close matches listed twice: {dupes}")
        if strict := sorted({c.ingredient for c in self.close_matches} & set(cuts)):
            raise ValueError(f"a chicken cut is never a close match (M6): {strict}")
        return self
