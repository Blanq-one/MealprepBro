"""Objective weights and nutrient scores (BUILD_PLAN §9 Phase 1, deliverable 12).

All terms are normalized to "points": a nutrient term is worth up to about 1 point per portion, cost is
counted per dollar, kcal deviation per kcal. Grocery mode shifts the balance between cost and nutrition.

Protein is never rewarded: the daily protein target is a hard floor in the model, and protein above it
earns nothing (so "protein" as a priority adds no score term, and "balanced" scores fiber only).
"""

from dataclasses import dataclass, replace
from decimal import Decimal

from app.domain.enums import GroceryMode, NutritionPriority
from app.planning.problem import CandidateRecipe

FIBER_DV_G = Decimal(28)


@dataclass(frozen=True)
class Weights:
    primary: float = 1.0  # per portion, nutrient score normalized to the best candidate
    secondary: float = 0.4
    preference: float = 0.3  # favorites up, disliked ingredients down
    cost_per_dollar: float = 0.5  # cash spent this trip (whole packages)
    waste_per_dollar: float = 0.5  # perishable purchases left over
    # extra, per dollar of a perishable package left beyond SMALL_FRACTION_LEFT of it: opening a pack for a
    # sliver of it
    small_fraction_per_dollar: float = 1.5
    inventory_use: float = 2.0  # using up an open package or an expiring lot completely
    slot_deviation_per_kcal: float = 0.004
    week_kcal_toward_target: float = 0.002  # per kcal planned; the ceilings cap it at your target
    batch: float = 0.3  # each extra cook batch
    from_freezer: float = 0.05  # small preference for fresh leftovers over thawed ones
    never_favored_tiebreak: float = 0.05  # per portion: an otherwise-equal capped recipe always loses


def weights_for(mode: GroceryMode) -> Weights:
    base = Weights()
    if mode is GroceryMode.CHEAPEST:
        return replace(
            base, cost_per_dollar=1.5, waste_per_dollar=1.5, small_fraction_per_dollar=3.0, primary=0.6
        )
    if mode is GroceryMode.HEALTHIER:
        return replace(base, cost_per_dollar=0.25, primary=1.5, secondary=0.8)
    return base  # balanced; seasonal behaves like balanced until Phase 5 adds seasonality data


def nutrient_score(candidate: CandidateRecipe, priority: NutritionPriority) -> Decimal:
    """Per portion at multiplier 1. Iron counts heme iron twice (better absorbed; the heme share is an
    estimate). Protein scores 0: it is a target (a floor), not something to maximize. Balanced = fiber as a
    fraction of its daily value (protein is covered by the target)."""
    p = candidate.per_portion
    if priority is NutritionPriority.PROTEIN:
        return Decimal(0)
    if priority is NutritionPriority.CARB:
        return p.get("carbohydrate_g", Decimal(0))
    if priority is NutritionPriority.IRON:
        return p.get("iron_mg", Decimal(0)) + candidate.heme_iron_mg
    return p.get("fiber_g", Decimal(0)) / FIBER_DV_G
