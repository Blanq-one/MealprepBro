"""Budget tiers (step 2b.6, AA6, AA8): the seed's price tier per ingredient, what a tier lets a plan buy and
its variety, the three cards' quick estimates, and a full plan for the tier you tap."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.tests.test_meal_prep_api import meal_prep, plan_of
from app.db.models import GroceryList, GroceryListItem, Ingredient, MealPlan
from app.domain.price_tiers import CHEAP_PROTEIN_PER_DOLLAR, PriceTier, may_buy, tier_from_protein
from app.domain.units import convert
from app.planning.inputs import constraints_for
from app.planning.loader import load_ingredient_plans
from app.schemas.plans import PlanRequest
from app.services.ingredient_data import load_ingredients
from app.services.pricing import active_stores
from app.services.settings import current_user

THREE_DAYS = {
    "shape": "days",
    "day_count": 3,
    "slots": ["lunch", "dinner"],
    "start": "today",
    "cook_style": "mix",
}


def tiers(session: Session) -> dict[str, tuple[str | None, str | None]]:
    return {i.slug: (i.price_tier, i.price_tier_basis) for i in session.scalars(select(Ingredient))}


def test_your_examples_land_in_their_tiers_and_seasonings_in_none(seeded_db: Session) -> None:
    t = tiers(seeded_db)
    for slug in ("chicken-thigh-boneless-skinless", "egg-large", "lentils-red", "rice-long-grain-white"):
        assert t[slug][0] == "cheap", slug
    for slug in ("peas-frozen", "broccoli-frozen", "flour-tortilla-small"):
        assert t[slug][0] == "cheap", slug
    # some Greek yogurt and the basic salad vegetables in Cheapest; A bit better adds more fresh veg
    for slug in ("greek-yogurt-nonfat", "tomato", "cucumber", "romaine"):
        assert t[slug][0] == "cheap", slug
    for slug in (
        "chicken-breast-boneless-skinless",
        "ground-turkey-93",
        "bell-pepper",
        "broccoli",
        "spinach",
    ):
        assert t[slug][0] == "better", slug
    assert t["salmon"][0] == t["shrimp"][0] == "fancy"
    for slug in ("salt", "cumin-ground", "olive-oil", "soy-sauce" if "soy-sauce" in t else "salt"):
        assert t[slug] == (None, None), slug  # seasonings and oils work in every tier
    assert all((tier is None) == (basis is None) for tier, basis in t.values())
    assert {basis for _, basis in t.values()} == {None, "named", "protein_per_dollar", "estimate"}


def test_derived_tiers_follow_protein_per_dollar_at_the_seed_prices(seeded_db: Session) -> None:
    data = load_ingredients(seeded_db)
    plans = load_ingredient_plans(seeded_db, 0, data.keys(), [s.id for s in active_stores(seeded_db)])
    rows = {i.slug: i for i in seeded_db.scalars(select(Ingredient))}
    derived = [r for r in rows.values() if r.price_tier_basis == "protein_per_dollar"]
    assert len(derived) >= 10
    for row in derived:
        d, plan = data[row.id], plans[row.id]
        assert plan.offers, row.slug  # derived only where the seed prices it
        cents_per_g = min(o.cents_per_unit for o in plan.offers) / convert(
            Decimal(1), plan.planning_unit, "g", d.units
        )
        protein_per_g = d.profile.per_100g.get("protein_g", Decimal(0)) * d.profile.edible_fraction / 100
        assert row.price_tier == tier_from_protein(protein_per_g / cents_per_g * 100).value, row.slug
    assert tier_from_protein(CHEAP_PROTEIN_PER_DOLLAR) == "cheap"


def test_a_tier_limits_what_a_plan_buys_and_sets_its_variety(seeded_db: Session) -> None:
    user = current_user(seeded_db)
    rows = list(seeded_db.scalars(select(Ingredient).where(Ingredient.archived_at.is_(None))))
    for tier, most in ((PriceTier.CHEAPEST, 5), (PriceTier.BETTER, 4), (PriceTier.FANCY, 3)):
        request = PlanRequest(week_start="2026-10-14", days=3, price_tier=tier, allow_llm=False)
        c = constraints_for(seeded_db, user.id, request)
        assert c.price_tier == tier.value and c.max_portions_per_recipe == most
        assert c.allowed_purchase_ingredient_ids is not None
        for row in rows:
            if row.id in c.excluded_ingredient_ids:
                continue
            assert c.may_buy(row.id) == may_buy(tier, row.price_tier), (tier, row.slug)
    assert may_buy(PriceTier.CHEAPEST, None) and not may_buy(PriceTier.CHEAPEST, "better")
    assert may_buy(PriceTier.FANCY, "fancy") and not may_buy(PriceTier.BETTER, "fancy")


def test_three_cards_with_estimates_then_a_full_plan_for_the_tier_you_tap(
    api: Any, seeded_db: Session
) -> None:
    answers = {"mode": "prep", "prep": THREE_DAYS, "shopping": "make_a_list"}
    reply = api.post("/api/v1/cook/meal-prep/tiers", json=answers)
    assert reply.status_code == 200, reply.text
    cards = reply.json()
    assert [c["tier"] for c in cards] == ["cheapest", "better", "fancy"]
    assert [c["label"] for c in cards] == ["Cheapest", "A bit better", "Fancy"]
    estimated = [c for c in cards if c["status"] == "estimated"]
    assert estimated, cards
    for card in estimated:
        assert card["total_display"].startswith("about $") and card["total_cents"] > 0
        assert card["protein_per_day_display"].startswith("about ") and card[
            "protein_per_day_display"
        ].endswith("g protein a day")
    for card in cards:
        if card["status"] == "none_fits":
            assert card["reason"]
    plan = plan_of(meal_prep(api, prep=THREE_DAYS, shopping="make_a_list", price_tier="cheapest"))
    row = seeded_db.get(MealPlan, plan["id"])
    assert row is not None and row.constraints["price_tier"] == "cheapest"
    assert row.constraints["max_portions_per_recipe"] == 5
    glist = seeded_db.scalars(select(GroceryList).where(GroceryList.meal_plan_id == plan["id"])).one()
    rows = {i.id: i for i in seeded_db.scalars(select(Ingredient))}
    for item in seeded_db.scalars(select(GroceryListItem).where(GroceryListItem.grocery_list_id == glist.id)):
        if (item.reason or {}).get("kind") == "buy" and item.to_buy_quantity > 0:
            assert may_buy(PriceTier.CHEAPEST, rows[item.ingredient_id].price_tier), rows[
                item.ingredient_id
            ].slug


def test_set_my_own_limit_is_a_budget_number_instead(api: Any) -> None:
    plan = plan_of(meal_prep(api, prep=THREE_DAYS, shopping="make_a_list", budget_cents=6000))
    assert plan["purchase_limit_cents"] == 6000
