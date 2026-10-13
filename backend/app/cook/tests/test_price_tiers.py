"""Budget tiers (step 2b.6, AA6, AA8; four tiers since its approval, items 1-3 and 5): the seed's price tier
per ingredient (Broke's staples, protein foods by protein per dollar), what a tier lets a plan buy, its
variety, the upgrades it includes, the four cards' quick estimates, and a full plan for the tier you tap."""

import json
from dataclasses import replace
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.prep import resolve_prep
from app.cook.tests.conftest import add_recipe
from app.cook.tests.test_meal_prep_api import meal_prep, plan_of
from app.cook.tiers import protein_line
from app.db.models import GroceryList, GroceryListItem, Ingredient, MealPlan
from app.domain.enums import GroceryMode, MealSlot
from app.domain.price_tiers import (
    CHEAP_PROTEIN_PER_DOLLAR,
    PriceTier,
    may_buy,
    tier_from_protein,
    upgrade_minimums,
    upgrade_slots,
)
from app.domain.units import convert
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem, load_ingredient_plans
from app.planning.solver.model import SolverSolution
from app.planning.solver.solve import solve
from app.schemas.cook import CookAnswers
from app.schemas.plans import PlanRequest
from app.seed.files import load_seed_files
from app.services.ingredient_data import load_ingredients
from app.services.pricing import active_stores
from app.services.settings import current_user
from app.testing import factories as f

THREE_DAYS = {
    "shape": "days",
    "day_count": 3,
    "slots": ["lunch", "dinner"],
    "start": "today",
    "cook_style": "mix",
}


def tiers(session: Session) -> dict[str, tuple[str | None, str | None]]:
    return {i.slug: (i.price_tier, i.price_tier_basis) for i in session.scalars(select(Ingredient))}


def test_brokes_staples_protein_by_the_dollar_and_seasonings_in_every_tier(seeded_db: Session) -> None:
    t = tiers(seeded_db)
    # your Broke list (item 2): rice, lentils, eggs, chickpeas, oats, frozen veg, tortillas, family-pack
    # chicken
    for slug in (
        "rice-long-grain-white",
        "lentils-red",
        "egg-large",
        "chickpeas-canned",
        "rolled-oats",
        "peas-frozen",
        "broccoli-frozen",
        "spinach-frozen",
        "flour-tortilla-small",
        "chicken-thigh-boneless-skinless",
        "chicken-drumstick",
    ):
        assert t[slug] == ("staple", "staple"), slug
    # item 5: chicken breast is in Cheapest (a staple: Broke's family-pack chicken)
    assert t["chicken-breast-boneless-skinless"][0] == "staple"
    assert may_buy(PriceTier.CHEAPEST, "staple") and may_buy(PriceTier.BROKE, "staple")
    # other protein foods follow protein per dollar at your stores, not a list
    assert t["ground-turkey-93"] == ("better", "protein_per_dollar")
    assert t["greek-yogurt-nonfat"] == ("cheap", "protein_per_dollar")
    assert t["salmon"] == t["shrimp"] == ("fancy", "protein_per_dollar")
    for slug in ("bell-pepper", "broccoli", "spinach"):
        assert t[slug][0] == "better", slug  # A bit better's fresh veg
    for slug in ("salt", "cumin-ground", "olive-oil"):
        assert t[slug] == (None, None), slug  # seasonings and oils work in every tier
    assert all((tier is None) == (basis is None) for tier, basis in t.values())
    assert {basis for _, basis in t.values()} == {None, "staple", "named", "protein_per_dollar", "estimate"}


def test_derived_tiers_follow_protein_per_dollar_at_the_seed_prices(seeded_db: Session) -> None:
    data = load_ingredients(seeded_db)
    plans = load_ingredient_plans(seeded_db, 0, data.keys(), [s.id for s in active_stores(seeded_db)])
    rows = {i.slug: i for i in seeded_db.scalars(select(Ingredient))}
    derived = [r for r in rows.values() if r.price_tier_basis == "protein_per_dollar"]
    assert len(derived) >= 12
    for row in derived:
        d, plan = data[row.id], plans[row.id]
        assert plan.offers, row.slug  # derived only where the seed prices it
        cents_per_g = min(o.cents_per_unit for o in plan.offers) / convert(
            Decimal(1), plan.planning_unit, "g", d.units
        )
        protein_per_g = d.profile.per_100g.get("protein_g", Decimal(0)) * d.profile.edible_fraction / 100
        assert row.price_tier == tier_from_protein(protein_per_g / cents_per_g * 100).value, row.slug
    assert tier_from_protein(CHEAP_PROTEIN_PER_DOLLAR) == "cheap"


def test_a_tier_sets_what_a_plan_buys_its_variety_and_its_upgrades(seeded_db: Session) -> None:
    user = current_user(seeded_db)
    rows = list(seeded_db.scalars(select(Ingredient).where(Ingredient.archived_at.is_(None))))
    powder = next(r for r in rows if r.slug == "protein-powder-double-chocolate")
    variety = {PriceTier.BROKE: 7, PriceTier.CHEAPEST: 5, PriceTier.BETTER: 4, PriceTier.FANCY: 3}
    for tier, most in variety.items():
        request = PlanRequest(
            week_start="2026-10-14", days=7, price_tier=tier, allow_llm=False, protein_reward=True
        )
        c = constraints_for(seeded_db, user.id, request)
        assert c.price_tier == tier.value and c.max_portions_per_recipe == most
        assert c.grocery_mode is GroceryMode.CHEAPEST  # every tier stays cost-aware within its own rules
        # Broke and Cheapest never chase protein (item 1); the higher tiers' reward stops at the band's top
        assert c.protein_reward is (tier not in (PriceTier.BROKE, PriceTier.CHEAPEST))
        assert c.daily_protein_target_g == 100 and c.daily_protein_max_g == 110
        assert c.allowed_purchase_ingredient_ids is not None
        for row in rows:
            if row.id in c.excluded_ingredient_ids:
                continue
            assert c.may_buy(row.id) == may_buy(tier, row.price_tier), (tier, row.slug)
        mains = sum(1 for d in c.days for s in d.slots if s in upgrade_slots(d.slots))
        assert (c.upgraded_meals_min, c.premium_meals_min) == upgrade_minimums(tier, mains)
    assert not may_buy(PriceTier.BROKE, powder.price_tier)  # never a new tub of protein powder in Broke
    assert upgrade_minimums(PriceTier.BETTER, 14) == (4, 0) and upgrade_minimums(PriceTier.FANCY, 14) == (
        4,
        4,
    )
    assert upgrade_minimums(PriceTier.CHEAPEST, 14) == (0, 0) and upgrade_minimums(PriceTier.FANCY, 1) == (
        1,
        1,
    )


def test_a_tier_includes_its_upgrades_rather_than_only_allowing_them() -> None:
    """Item 2: with a pricier upgraded dinner on offer, a week with no upgrades to include picks the cheap one
    every day; one that includes 2 has exactly 2 (rewarded up to that count), never more."""
    ing = {
        1: f.food(1, "lentils", 100, protein=10, offers=[f.offer(1, cents_per_unit="0.30")]),
        # $7 a meal more than the lentils: well past the solver's one-point gap, well under the upgrade reward
        2: f.food(2, "salmon", 100, protein=12, offers=[f.offer(2, cents_per_unit="1.50")]),
    }
    cheap = f.recipe(10, "Lentil stew", [MealSlot.DINNER], [f.line(1, 590)], ing, base=1)
    fancy = f.recipe(11, "Salmon bowl", [MealSlot.DINNER], [f.line(2, 590)], ing, base=1)
    upgraded = replace(fancy, tier_rank=2)
    base = f.constraints(days=3, slots={MealSlot.DINNER: 600}, cook_weekdays=range(7), max_portions=3)

    def salmon_meals(c: Any) -> int:
        p = f.problem(c, [cheap, upgraded], ing)
        result = solve(p, time_limit_s=30)
        assert isinstance(result, SolverSolution), result
        return sum(1 for m in result.meals if result.batches[m.batch_index].version_id == 11)

    assert salmon_meals(base) == 0  # only allowed: the cost decides
    assert salmon_meals(base.model_copy(update={"upgraded_meals_min": 2})) == 2  # included, and no more


def test_unpriced_items_are_never_free_in_a_tier(seeded_db: Session) -> None:
    """A tier is a price claim: a recipe needing an item with no price at your stores (and none in your
    pantry) is left out, saying why, instead of counting the item as free."""
    user = current_user(seeded_db)
    kale = add_recipe(  # kale has no price at your stores
        seeded_db,
        "Kale chicken bowl",
        [("chicken-thigh-boneless-skinless", 400, "g", "protein"), ("kale", 150, "g", "vegetable")],
    )
    request = PlanRequest(week_start="2026-10-14", days=3, price_tier=PriceTier.FANCY, allow_llm=False)
    p = build_problem(seeded_db, user.id, constraints_for(seeded_db, user.id, request))
    unpriced = [e for e in p.excluded if "unpriced" in e.codes]
    assert kale.id in {e.version_id for e in unpriced}
    assert all("the Fancy tier can't count it" in " ".join(e.reasons) for e in unpriced)
    plain = build_problem(
        seeded_db,
        user.id,
        constraints_for(seeded_db, user.id, request.model_copy(update={"price_tier": None})),
    )
    assert {e.version_id for e in unpriced} <= {
        r.version_id for r in plain.candidates
    }  # without a tier: fine


def test_four_cards_with_estimates_then_a_full_plan_for_the_tier_you_tap(
    api: Any, seeded_db: Session
) -> None:
    answers = {"mode": "prep", "prep": THREE_DAYS, "shopping": "make_a_list"}
    reply = api.post("/api/v1/cook/meal-prep/tiers", json=answers)
    assert reply.status_code == 200, reply.text
    result = json.loads(reply.text.splitlines()[-1])  # NDJSON since AC6: the result line has all four
    assert result["event"] == "result", result
    cards = result["cards"]
    assert [c["tier"] for c in cards] == ["broke", "cheapest", "better", "fancy"]
    assert [c["label"] for c in cards] == ["Broke mode", "Cheapest", "A bit better", "Fancy"]
    estimated = [c for c in cards if c["status"] == "estimated"]
    assert len(estimated) >= 2, cards
    for card in estimated:
        assert card["total_display"].startswith("about $") and card["total_cents"] >= 0
        # lunch + dinner is part of your day: the line says so (item 3)
        assert card["protein_per_day_display"].startswith("Lunch + dinner: about ")
        assert card["protein_per_day_display"].endswith("g of your 100 g daily target")
        assert card["includes_display"]
        if card["stock_up_cents"]:
            assert (
                card["stock_up_display"].startswith("+ about $") and " stock-up: " in card["stock_up_display"]
            )
        else:
            assert card["stock_up_display"] is None
    for card in cards:
        if card["status"] != "estimated":
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


def test_a_whole_day_plan_says_protein_a_day() -> None:
    settings = load_seed_files().settings
    every = [a.slot.value for a in settings.slot_allocations]
    answers = CookAnswers.model_validate(
        {"mode": "prep", "prep": {**THREE_DAYS, "slots": every}, "shopping": "make_a_list"}
    )
    plan = resolve_prep(answers, settings, f.MONDAY)
    assert protein_line(104, plan, settings) == "about 104 g protein a day"


def test_set_my_own_limit_is_a_budget_number_instead(api: Any) -> None:
    plan = plan_of(meal_prep(api, prep=THREE_DAYS, shopping="make_a_list", budget_cents=6000))
    assert plan["purchase_limit_cents"] == 6000
