"""RoundedPlan: the plan after practical rounding, the absorption pass and exact grocery math (§2.5).

It is the only thing downstream code ever sees. The plan validator accepts nothing else, so raw solver
output (fractional multipliers, unrounded quantities) can never be validated or persisted by mistake.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
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
    kind: str  # buy | from_inventory | staple | unpriced
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
            "meals": self.meals,
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
    notes: tuple[str, ...] = field(default_factory=tuple)
