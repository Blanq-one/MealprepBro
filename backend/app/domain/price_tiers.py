"""Budget tiers (step 2b.6, AA6, AA8; four tiers since the 2b.6 approval, items 2 and 5). Pure, no DB.

Each ingredient carries a price tier: staple, cheap, better or fancy, or none for seasonings, oils and
condiments (they work in every tier). A plan's tier limits what it buys and, above Cheapest, includes its
upgrades rather than only allowing them:

  Broke mode    rock-bottom spend: staples only (rice, lentils, eggs, chickpeas, oats, frozen veg,
                tortillas, family-pack chicken, and the basics to cook them: onions, potatoes, carrots,
                cabbage, canned tomatoes, flour, milk), your pantry first, repeats fine (a recipe up to 7
                times a week), and no stock-up purchase unless it's needed (each counts at its whole pack;
                never a new tub of protein powder)
  Cheapest      cheap staples, with a little more variety (5 a week)
  A bit better  at least a few meals use an upgraded item (a better or fancy one), more variety (4)
  Fancy         several meals use a premium protein (salmon, shrimp and similar), the most variety (3)

What you already have, Always-have items and your could-buy items work in every tier. Every tier stays
cost-aware within its own rules, meets your calories and your protein floor, and never chases protein above
your band (Broke and Cheapest earn no protein reward at all).

An ingredient bought for its protein is tiered by protein per dollar at your stores' cheapest price (at least
20 g a dollar is cheap, at least 12 better, less fancy), unless it is on Broke's staple list; the rest are
the staple list, your examples (AA6) or estimates, flagged as such in the seed data and the review sheet.
"""

from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from math import ceil

from app.domain.enums import MealSlot


class IngredientTier(StrEnum):
    STAPLE = "staple"  # Broke mode's staples (also in every higher tier)
    CHEAP = "cheap"
    BETTER = "better"
    FANCY = "fancy"


class TierBasis(StrEnum):
    PROTEIN_PER_DOLLAR = "protein_per_dollar"
    STAPLE = "staple"  # Broke mode's staple list (2b.6 approval, item 2)
    NAMED = "named"  # your examples (AA6)
    ESTIMATE = "estimate"


class PriceTier(StrEnum):
    """A plan's tier (the cards in the shopping step)."""

    BROKE = "broke"
    CHEAPEST = "cheapest"
    BETTER = "better"
    FANCY = "fancy"


CHEAP_PROTEIN_PER_DOLLAR = Decimal(20)  # grams of protein a dollar buys
BETTER_PROTEIN_PER_DOLLAR = Decimal(12)
RANK = {IngredientTier.STAPLE: 0, IngredientTier.CHEAP: 1, IngredientTier.BETTER: 2, IngredientTier.FANCY: 3}
PLAN_RANK = {PriceTier.BROKE: 0, PriceTier.CHEAPEST: 1, PriceTier.BETTER: 2, PriceTier.FANCY: 3}
MAX_PORTIONS = {PriceTier.BROKE: 7, PriceTier.CHEAPEST: 5, PriceTier.BETTER: 4, PriceTier.FANCY: 3}
LABELS = {
    PriceTier.BROKE: "Broke mode",
    PriceTier.CHEAPEST: "Cheapest",
    PriceTier.BETTER: "A bit better",
    PriceTier.FANCY: "Fancy",
}
BLURBS = {
    PriceTier.BROKE: "Rock bottom: your pantry first, then rice, lentils, eggs, chickpeas, oats, frozen veg, "
    "tortillas, family-pack chicken; repeats are fine",
    PriceTier.CHEAPEST: "Cheap staples, a little more variety",
    PriceTier.BETTER: "A few meals with upgrades (Greek yogurt, ground turkey, fresh veg), more variety",
    PriceTier.FANCY: "Several meals with salmon, shrimp and other premium picks, the most variety",
}
# a recipe "uses" an ingredient's tier when a counted line has at least this much of it per portion (so a
# garnish of a pricier herb doesn't make a meal an upgrade)
UPGRADE_MIN_GRAMS = Decimal(25)
PREMIUM_MIN_GRAMS = Decimal(50)  # a premium protein's share of a portion
# the tiers' own price behavior: Broke and Cheapest plan on cost first and never earn a protein reward
COST_FIRST = frozenset({PriceTier.BROKE, PriceTier.CHEAPEST})


MAIN_SLOTS = frozenset({MealSlot.LUNCH, MealSlot.DINNER})
MEAL_SLOTS = frozenset({MealSlot.BREAKFAST, MealSlot.LUNCH, MealSlot.DINNER})


def upgrade_slots(planned: Iterable[MealSlot]) -> frozenset[MealSlot]:
    """The meals a tier's upgrades count in: lunches and dinners, or breakfasts when the plan has neither."""
    slots = frozenset(planned)
    return (slots & MAIN_SLOTS) or (slots & MEAL_SLOTS)


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


def tier_rank(ingredient_tier: str | None) -> int:
    """An ingredient's tier as a number (none counts as a staple: it never makes a meal an upgrade)."""
    return RANK[IngredientTier(ingredient_tier)] if ingredient_tier is not None else 0


def upgrade_minimums(tier: PriceTier, main_meals: int) -> tuple[int, int]:
    """(meals with an upgraded item, meals with a premium protein) a tier includes, for a plan of this many
    main meals (lunches and dinners; every capped meal when it has neither): A bit better at least a quarter
    of them (2 or more), Fancy as many with a premium protein. Never more than the plan has."""
    if main_meals <= 0 or tier in COST_FIRST:
        return 0, 0
    few = min(main_meals, max(2, ceil(main_meals / 4)))
    if tier is PriceTier.BETTER:
        return few, 0
    return few, few
