"""The planning problem as plain data: candidate recipes, purchase offers, inventory and the constraints.

Built from the database by planning/loader.py, or directly by tests. The solver, the post-solve rounding
and the absorption pass are pure functions of this object.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.domain.enums import Equipment, MealSlot, PortionSize, RecipeMood
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
    perishable: bool = False
    shelf_life_days_fridge: int | None = None
    offers: tuple[Offer, ...] = ()
    lots: tuple[InventoryLot, ...] = ()

    def to_planning(self, quantity: Decimal, unit: str) -> Decimal:
        return convert(quantity, unit, self.planning_unit, self.units)

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


@dataclass(frozen=True)
class Tightening:
    """Bounds tightened by the orchestrator after the validator caught a rounding problem."""

    day_ceiling: Mapping[date, int] = field(default_factory=dict)  # kcal to subtract from a day's ceiling
    day_floor: Mapping[date, int] = field(default_factory=dict)  # kcal to add to a day's floor
    week_ceiling: int = 0
    week_floor: int = 0
    budget_cents: int = 0  # cents to subtract from the hard budget
    # observed rounding bias per recipe version: kcal per portion that practical rounding added (or removed)
    kcal_bias: Mapping[int, Decimal] = field(default_factory=dict)

    def merged(self, other: "Tightening") -> "Tightening":
        def add(a: Mapping[date, int], b: Mapping[date, int]) -> dict[date, int]:
            return {d: a.get(d, 0) + b.get(d, 0) for d in set(a) | set(b)}

        bias = dict(self.kcal_bias)
        bias.update(other.kcal_bias)  # the latest observation wins
        return Tightening(
            add(self.day_ceiling, other.day_ceiling),
            add(self.day_floor, other.day_floor),
            self.week_ceiling + other.week_ceiling,
            self.week_floor + other.week_floor,
            self.budget_cents + other.budget_cents,
            bias,
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
