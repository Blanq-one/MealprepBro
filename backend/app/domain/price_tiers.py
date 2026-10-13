"""Budget tiers (step 2b.6, AA6, AA8). Pure, no DB.

Each ingredient carries a price tier: cheap, better or fancy, or none for seasonings, oils and condiments
(they work in every tier). A plan's tier limits what it buys:

  Cheapest      cheap staples: chicken thighs, eggs, lentils, rice, frozen vegetables, tortillas
  A bit better  adds chicken breast, more Greek yogurt, ground turkey, more fresh vegetables
  Fancy         adds premium items such as salmon and shrimp

What you already have, Always-have items and your could-buy items work in every tier. Variety grows with the
tier: at most 5 portions of one recipe a week in Cheapest, 4 in A bit better, 3 in Fancy.

An ingredient's tier rests on protein per dollar at your stores' cheapest price when protein is what it's
bought for (at least 25 g a dollar is cheap, at least 12 better, less fancy); your examples (AA6) where they
name one; and an estimate otherwise (flagged as such in the seed data and the review sheet).
"""

from decimal import Decimal
from enum import StrEnum


class IngredientTier(StrEnum):
    CHEAP = "cheap"
    BETTER = "better"
    FANCY = "fancy"


class TierBasis(StrEnum):
    PROTEIN_PER_DOLLAR = "protein_per_dollar"
    NAMED = "named"  # your examples (AA6)
    ESTIMATE = "estimate"


class PriceTier(StrEnum):
    """A plan's tier (the cards in the shopping step)."""

    CHEAPEST = "cheapest"
    BETTER = "better"
    FANCY = "fancy"


CHEAP_PROTEIN_PER_DOLLAR = Decimal(25)  # grams of protein a dollar buys
BETTER_PROTEIN_PER_DOLLAR = Decimal(12)
RANK = {IngredientTier.CHEAP: 0, IngredientTier.BETTER: 1, IngredientTier.FANCY: 2}
PLAN_RANK = {PriceTier.CHEAPEST: 0, PriceTier.BETTER: 1, PriceTier.FANCY: 2}
MAX_PORTIONS = {PriceTier.CHEAPEST: 5, PriceTier.BETTER: 4, PriceTier.FANCY: 3}
LABELS = {PriceTier.CHEAPEST: "Cheapest", PriceTier.BETTER: "A bit better", PriceTier.FANCY: "Fancy"}
BLURBS = {
    PriceTier.CHEAPEST: "Cheap staples: chicken thighs, eggs, lentils, rice, frozen veg, tortillas",
    PriceTier.BETTER: "Adds chicken breast, Greek yogurt, ground turkey and more fresh veg",
    PriceTier.FANCY: "Adds salmon, shrimp and other premium picks, with more variety",
}


def tier_from_protein(grams_per_dollar: Decimal) -> IngredientTier:
    if grams_per_dollar >= CHEAP_PROTEIN_PER_DOLLAR:
        return IngredientTier.CHEAP
    if grams_per_dollar >= BETTER_PROTEIN_PER_DOLLAR:
        return IngredientTier.BETTER
    return IngredientTier.FANCY


def may_buy(plan_tier: PriceTier, ingredient_tier: str | None) -> bool:
    """Whether a plan of this tier may buy an ingredient of that tier (none = any tier)."""
    if ingredient_tier is None:
        return True
    return RANK[IngredientTier(ingredient_tier)] <= PLAN_RANK[plan_tier]
