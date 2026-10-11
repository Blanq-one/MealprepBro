"""RoundedPlan: the plan after practical rounding, the absorption pass and exact grocery math (§2.5).

It is the only thing downstream code ever sees. The plan validator accepts nothing else, so raw solver
output (fractional multipliers, unrounded quantities) can never be validated or persisted by mistake.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.domain.enums import MealSlot, PortionSize
from app.planning.problem import size_multiplier
from app.schemas.constraints import PlanConstraints

ABSORBED = "absorbed_full_package"
SUBSTITUTED = "substituted"


@dataclass(frozen=True)
class RoundedLine:
    recipe_ingredient_id: int | None
    ingredient_id: int
    name: str
    amount: Decimal  # practical amount in `unit` (what the cook measures)
    unit: str  # display unit
    base_quantity: Decimal  # stored base quantity, g / ml / count (3 dp)
    base_unit: str
    optional: bool = False
    adjustment: str | None = None


@dataclass(frozen=True)
class RoundedBatch:
    version_id: int
    title: str
    cook_on: date
    portions: int
    portions_to_freeze: int
    portion_size: PortionSize
    nudge: Decimal  # the solver's fine-tuning multiplier
    absorption_scale: Decimal  # 1 unless the batch was scaled up to use a whole package (R5)
    scale_factor: Decimal  # applied to the authored quantities: portions × size × nudge × absorption / base
    planned_minutes: int  # hands-on minutes
    lines: tuple[RoundedLine, ...]
    per_portion: Mapping[str, Decimal]  # from the rounded lines
    absorbed_ingredient_id: int | None = None
    total_minutes: int = 0  # start to finish, as the recipe states it
    no_cook: bool = False  # no cooking equipment: its waiting time is chilling or soaking in the fridge

    @property
    def passive_minutes(self) -> int:
        return max(self.total_minutes - self.planned_minutes, 0)

    @property
    def portion_multiplier(self) -> Decimal:
        return size_multiplier(self.portion_size) * self.nudge * self.absorption_scale


@dataclass(frozen=True)
class RoundedMeal:
    eat_on: date
    slot: MealSlot
    batch_index: int
    from_freezer: bool
    kcal: int  # half-up per meal (§7.1)
    protein_g: Decimal


@dataclass(frozen=True)
class GroceryItem:
    ingredient_id: int
    name: str
    unit: str  # the ingredient's planning unit
    needed: Decimal
    inventory_used: Decimal
    to_buy: Decimal
    kind: str  # buy | from_inventory | staple | unpriced | always_have (never listed)
    product_id: int | None = None
    store_id: int | None = None
    observation_id: int | None = None
    packages: int | None = None
    bought: Decimal | None = None  # quantity this line buys
    cost_cents: int | None = None
    remainder: Decimal | None = None
    is_estimate: bool = False
    perishable: bool = False
    recipes: tuple[str, ...] = ()
    note: str | None = None
    stock_up: bool = False  # long-life, bought occasionally: listed apart, outside a shop-mode budget


@dataclass(frozen=True)
class GroceryPlan:
    items: tuple[GroceryItem, ...]
    store_cents: Mapping[int, int]
    total_cents: int
    complete: bool
    unpriced: tuple[str, ...]
    split: bool
    primary_only_cents: int | None
    savings_cents: int
    forced_elsewhere: tuple[str, ...] = ()
    inventory_takes: tuple[tuple[int, Decimal], ...] = ()  # (lot id, quantity in the lot's planning unit)
    stock_up_cents: int = 0  # the part of total_cents spent on stock-up items

    @property
    def regular_cents(self) -> int:
        return self.total_cents - self.stock_up_cents


@dataclass(frozen=True)
class LeftoverItem:
    """Bought this trip and not used this week. It carries into your inventory."""

    ingredient_id: int
    name: str
    unit: str
    quantity: Decimal
    cents: int  # its share of what you paid
    fate: str  # freeze (raw meat, poultry, fish) | keeps | at_risk (perishable, likely to spoil)

    def to_json(self) -> dict[str, Any]:
        return {
            "ingredient_id": self.ingredient_id,
            "name": self.name,
            "unit": self.unit,
            "quantity": str(self.quantity),
            "cents": self.cents,
            "fate": self.fate,
        }


@dataclass(frozen=True)
class FreezeInstruction:
    """Raw meat, poultry or fish that won't be cooked within its fridge life (FoodSafety.gov chart): freeze
    it on shopping day. use_on None = no use planned this week (it carries into your inventory, frozen)."""

    ingredient_id: int
    name: str
    unit: str
    quantity: Decimal
    freeze_on: date
    fridge_days: int
    source: str  # purchase | inventory
    use_on: date | None = None
    recipe: str | None = None

    @property
    def thaw_on(self) -> date | None:
        """Thaw in the fridge the day before cooking."""
        return self.use_on - timedelta(days=1) if self.use_on is not None else None

    def to_json(self) -> dict[str, Any]:
        return {
            "ingredient_id": self.ingredient_id,
            "name": self.name,
            "unit": self.unit,
            "quantity": str(self.quantity),
            "freeze_on": self.freeze_on.isoformat(),
            "fridge_days": self.fridge_days,
            "source": self.source,
            "use_on": self.use_on.isoformat() if self.use_on else None,
            "recipe": self.recipe,
        }


@dataclass(frozen=True)
class MealCost:
    """One meal's share of its batch's cost (Phase 2b)."""

    eat_on: date
    slot: str
    batch_index: int
    cents: int


@dataclass(frozen=True)
class CostSummary:
    """The week's money (§7.1: integer cents; each ingredient is rounded once, totals are sums).

    cash + from_inventory = eaten + frozen_portions + leftover. Staples ("check you have") aren't counted;
    unpriced items make it incomplete. Phase 2b: each batch's cost (what it uses) and each meal's share of
    it; meal costs add up to their batch (with its frozen extras), and day costs to eaten."""

    cash_cents: int  # spent this trip, whole packages: the grocery list total (regular + stock-up)
    eaten_cents: int  # food eaten this week, whether bought now or taken from inventory
    from_inventory_cents: int  # what the week takes from inventory, at current prices
    leftover_cents: int  # bought and not used this week; carries into your inventory
    frozen_portions_cents: int  # cooked extra portions frozen for later weeks
    expected_waste_cents: int  # the at-risk part of the leftovers, plus inventory expiring unused
    complete: bool
    unpriced: tuple[str, ...] = ()
    stock_up_cash_cents: int = 0  # the part of cash_cents spent on stock-up items
    batch_cents: tuple[int, ...] = ()  # per batch, in plan order
    meal_costs: tuple[MealCost, ...] = ()  # per meal, in plan order

    @property
    def regular_cash_cents(self) -> int:
        return self.cash_cents - self.stock_up_cash_cents

    @property
    def day_cents(self) -> dict[date, int]:
        out: dict[date, int] = {}
        for meal in self.meal_costs:
            out[meal.eat_on] = out.get(meal.eat_on, 0) + meal.cents
        return out

    def to_json(self) -> dict[str, Any]:
        return {
            "cash_cents": self.cash_cents,
            "regular_cash_cents": self.regular_cash_cents,
            "stock_up_cash_cents": self.stock_up_cash_cents,
            "eaten_cents": self.eaten_cents,
            "from_inventory_cents": self.from_inventory_cents,
            "leftover_cents": self.leftover_cents,
            "frozen_portions_cents": self.frozen_portions_cents,
            "expected_waste_cents": self.expected_waste_cents,
            "complete": self.complete,
            "unpriced": list(self.unpriced),
            "batch_cents": list(self.batch_cents),
            "meal_cents": {meal_key(m.eat_on, m.slot): m.cents for m in self.meal_costs},
            "day_cents": {d.isoformat(): cents for d, cents in sorted(self.day_cents.items())},
        }


def meal_key(eat_on: date, slot: str) -> str:
    """How a stored plan finds a meal's cost: '2026-10-12/lunch' (one meal per day and slot)."""
    return f"{eat_on.isoformat()}/{slot}"


@dataclass(frozen=True)
class PlanTotals:
    day_kcal: Mapping[date, int]
    week_kcal: int
    day_protein_g: Mapping[date, Decimal]
    week_protein_g: Decimal
    cost_cents: int
    cost_complete: bool
    unpriced: tuple[str, ...]
    store_cents: Mapping[int, int]
    hands_on_minutes: Mapping[date, int]
    meals: int
    elapsed_minutes: Mapping[date, int] = field(default_factory=dict)  # per cook day, start to finish
    chill_minutes: Mapping[date, int] = field(default_factory=dict)  # longest fridge wait (no-cook recipes)
    protein_target_g: int = 0  # per day

    def to_json(self) -> dict[str, Any]:
        return {
            "day_kcal": {d.isoformat(): k for d, k in sorted(self.day_kcal.items())},
            "week_kcal": self.week_kcal,
            "day_protein_g": {d.isoformat(): str(p) for d, p in sorted(self.day_protein_g.items())},
            "week_protein_g": str(self.week_protein_g),
            "cost_cents": self.cost_cents,
            "cost_complete": self.cost_complete,
            "unpriced": list(self.unpriced),
            "store_cents": {str(k): v for k, v in sorted(self.store_cents.items())},
            "hands_on_minutes": {d.isoformat(): m for d, m in sorted(self.hands_on_minutes.items())},
            "elapsed_minutes": {d.isoformat(): m for d, m in sorted(self.elapsed_minutes.items())},
            "chill_minutes": {d.isoformat(): m for d, m in sorted(self.chill_minutes.items())},
            "meals": self.meals,
            "protein_target_g": self.protein_target_g,
        }


@dataclass(frozen=True)
class RoundedPlan:
    constraints: PlanConstraints
    batches: tuple[RoundedBatch, ...]
    meals: tuple[RoundedMeal, ...]
    grocery: GroceryPlan
    totals: PlanTotals
    solver_status: str
    solver_objective: float
    costs: CostSummary
    leftovers: tuple[LeftoverItem, ...] = ()
    freeze: tuple[FreezeInstruction, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)
    snapped: bool = True  # False: no nudge combination rounded into your limits (snap.py)
