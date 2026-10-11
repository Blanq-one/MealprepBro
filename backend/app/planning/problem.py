"""The planning problem as plain data: candidate recipes, purchase offers, inventory and the constraints.

Built from the database by planning/loader.py, or directly by tests. The solver, the post-solve rounding
and the absorption pass are pure functions of this object.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.domain.enums import Equipment, MealSlot, PortionSize, RecipeMood
from app.domain.fridge_life import FridgeLife
from app.domain.nutrition import NutritionProfile
from app.domain.purchase import Offer
from app.domain.scaling import PORTION_MULTIPLIERS
from app.domain.units import IngredientUnits, convert
from app.schemas.constraints import PlanConstraints

NUTRIENT_FOR_PRIORITY = {"protein": "protein_g", "carb": "carbohydrate_g", "iron": "iron_mg"}


@dataclass(frozen=True)
class RecipeLine:
    recipe_ingredient_id: int | None
    ingredient_id: int
    quantity: Decimal  # stored base quantity (g / ml / count) for base_servings
    unit: str
    authored_quantity: Decimal
    authored_unit: str
    optional: bool = False
    role: str = "other"


@dataclass(frozen=True)
class CandidateRecipe:
    version_id: int
    recipe_id: int
    title: str
    meal_slots: frozenset[MealSlot]
    mood: RecipeMood
    active_minutes: int
    equipment: frozenset[Equipment]
    freezer_friendly: bool
    base_servings: int
    lines: tuple[RecipeLine, ...]
    # computed by code from the stored lines (exact, unrounded), per portion at multiplier 1
    per_portion: Mapping[str, Decimal]
    heme_iron_mg: Decimal = Decimal(0)
    need_per_portion: Mapping[int, Decimal] = field(default_factory=dict)  # ingredient -> planning units
    cost_cents_per_portion: Decimal | None = None  # at unit prices, for never-favored neutralizing only
    total_minutes: int = 0
    origin: str = "seed"
    is_draft: bool = False
    never_favored: bool = False  # contains a member of a never-favored frequency cap (pork components)
    is_favorite: bool = False
    has_disliked: bool = False

    @property
    def kcal(self) -> Decimal:
        return self.per_portion.get("energy_kcal", Decimal(0))

    @property
    def protein_g(self) -> Decimal:
        return self.per_portion.get("protein_g", Decimal(0))

    @property
    def passive_minutes(self) -> int:
        return max(self.total_minutes - self.active_minutes, 0)

    @property
    def ingredient_ids(self) -> frozenset[int]:
        return frozenset(line.ingredient_id for line in self.lines)


@dataclass(frozen=True)
class InventoryLot:
    id: int
    ingredient_id: int
    quantity: Decimal  # in the ingredient's planning unit
    opened_on: date | None = None  # set = an open package
    expires_on: date | None = None
    acquired_on: date | None = None
    location: str | None = None  # fridge | freezer | pantry

    @property
    def opened(self) -> bool:
        return self.opened_on is not None


@dataclass(frozen=True)
class IngredientPlan:
    id: int
    name: str
    planning_unit: str  # g | ml | count: needs, offers and lots are all in this unit
    units: IngredientUnits
    profile: NutritionProfile
    count_rounding_step: Decimal = Decimal(1)
    staple: bool = False  # assume_in_stock: never bought by the plan, listed as "check you have"
    # Always have (settings, and water): unlimited stock you own. Never bought, never listed, its lots aren't
    # tracked by plans; what the week uses is costed at the unit price where one is known.
    always_have: bool = False
    stock_up: bool = False  # long-life, bought occasionally: outside a shop-mode budget, listed separately
    perishable: bool = False
    shelf_life_days_fridge: int | None = None
    location: str | None = None  # where it usually lives: fridge | freezer | pantry
    shelf_life_days_pantry: int | None = None
    shelf_life_days_freezer: int | None = None
    fridge_life: FridgeLife | None = None  # raw meat, poultry, fish and eggs (FoodSafety.gov chart)
    offers: tuple[Offer, ...] = ()
    lots: tuple[InventoryLot, ...] = ()

    @property
    def unlimited(self) -> bool:
        """The plan never buys it and never needs it from your lots: a staple or an Always-have item."""
        return self.staple or self.always_have

    def to_planning(self, quantity: Decimal, unit: str) -> Decimal:
        return convert(quantity, unit, self.planning_unit, self.units)

    def shelf_life_days(self) -> int | None:
        """How long it keeps where it usually lives (pantry, fridge or freezer); None = unknown."""
        if self.location == "pantry":
            return self.shelf_life_days_pantry
        if self.location == "freezer":
            return self.shelf_life_days_freezer
        return self.shelf_life_days_fridge

    def spoils_within(self, days: int) -> bool:
        """Perishable and not known to keep `days` days where it usually lives. Onions, garlic, potatoes
        and butter keep for weeks, so what's left of them isn't waste (no waste penalty, no absorption)."""
        if not self.perishable:
            return False
        life = self.shelf_life_days()
        return life is None or life < days

    @property
    def available(self) -> Decimal:
        return sum((lot.quantity for lot in self.lots), Decimal(0))

    def available_where(self, *, opened: bool | None = None, expiring_by: date | None = None) -> Decimal:
        total = Decimal(0)
        for lot in self.lots:
            if opened is not None and lot.opened != opened:
                continue
            if expiring_by is not None and (lot.expires_on is None or lot.expires_on > expiring_by):
                continue
            total += lot.quantity
        return total


@dataclass(frozen=True)
class ExcludedRecipe:
    version_id: int
    title: str
    meal_slots: frozenset[MealSlot]
    reasons: tuple[str, ...]
    held_ingredients: tuple[str, ...] = ()
    unpriced_ingredients: tuple[str, ...] = ()
    # one per reason kind, for the exposure log: excluded | held | frequency_cap | equipment | time |
    # nutrition_incomplete | unpriced | conversion
    codes: tuple[str, ...] = ()
    # why the time filter left it out (P4): "mood" = no cook day allows its mood; "minutes" = no such day has
    # enough hands-on time
    blocker: str | None = None
    mood: RecipeMood | None = None
    active_minutes: int | None = None


@dataclass(frozen=True)
class Tightening:
    """Bounds tightened by the orchestrator after the validator caught a rounding problem."""

    day_ceiling: Mapping[date, int] = field(default_factory=dict)  # kcal to subtract from a day's ceiling
    day_floor: Mapping[date, int] = field(default_factory=dict)  # kcal to add to a day's floor
    week_ceiling: int = 0
    week_floor: int = 0
    budget_cents: int = 0  # cents to subtract from the purchase limit
    # What practical rounding does to each recipe version's portion: rounded ≈ planned × scale + bias, where
    # planned = the exact per-portion value × size × nudge. A whole scoop doesn't shrink with a 0.9 nudge, so
    # the scale can be well under 1. Fitted before the first solve; re-solves replace the bias with what the
    # rounded plan showed.
    kcal_bias: Mapping[int, Decimal] = field(default_factory=dict)
    protein_bias: Mapping[int, Decimal] = field(default_factory=dict)  # the same, in grams of protein
    protein_day_floor: Mapping[date, Decimal] = field(default_factory=dict)  # grams to add to a day's floor
    protein_week_floor: Decimal = Decimal(0)
    # planning units to hold back from an ingredient's inventory, so rounding up doesn't spill into a
    # purchase the limit doesn't allow
    inventory_holdback: Mapping[int, Decimal] = field(default_factory=dict)
    kcal_scale: Mapping[int, Decimal] = field(default_factory=dict)  # default 1 (see kcal_bias)
    protein_scale: Mapping[int, Decimal] = field(default_factory=dict)

    def merged(self, other: "Tightening") -> "Tightening":
        def add[K, V: (int, Decimal)](a: Mapping[K, V], b: Mapping[K, V], zero: V) -> dict[K, V]:
            return {k: a.get(k, zero) + b.get(k, zero) for k in set(a) | set(b)}

        kcal_bias = {**self.kcal_bias, **other.kcal_bias}  # the latest observation wins
        protein_bias = {**self.protein_bias, **other.protein_bias}
        return Tightening(
            add(self.day_ceiling, other.day_ceiling, 0),
            add(self.day_floor, other.day_floor, 0),
            self.week_ceiling + other.week_ceiling,
            self.week_floor + other.week_floor,
            self.budget_cents + other.budget_cents,
            kcal_bias,
            protein_bias,
            add(self.protein_day_floor, other.protein_day_floor, Decimal(0)),
            self.protein_week_floor + other.protein_week_floor,
            add(self.inventory_holdback, other.inventory_holdback, Decimal(0)),
            {**self.kcal_scale, **other.kcal_scale},
            {**self.protein_scale, **other.protein_scale},
        )


@dataclass(frozen=True)
class PlanningProblem:
    constraints: PlanConstraints
    candidates: tuple[CandidateRecipe, ...]
    ingredients: Mapping[int, IngredientPlan]
    store_names: Mapping[int, str]
    excluded: tuple[ExcludedRecipe, ...] = ()
    tightening: Tightening = field(default_factory=Tightening)

    def candidate(self, version_id: int) -> CandidateRecipe:
        return next(c for c in self.candidates if c.version_id == version_id)

    def nudges(self) -> tuple[Decimal, ...]:
        pct = Decimal(str(self.constraints.portion_nudge_pct)) / 100
        if pct == 0:
            return (Decimal(1),)
        return (Decimal(1) - pct, Decimal(1), Decimal(1) + pct)

    def with_tightening(self, extra: Tightening) -> "PlanningProblem":
        return PlanningProblem(
            self.constraints,
            self.candidates,
            self.ingredients,
            self.store_names,
            self.excluded,
            self.tightening.merged(extra),
        )


def size_multiplier(size: PortionSize) -> Decimal:
    return PORTION_MULTIPLIERS[size.value]
