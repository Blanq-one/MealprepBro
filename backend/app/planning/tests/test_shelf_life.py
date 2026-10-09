"""Long-keeping fresh items (Phase 2 pre-work): onions, garlic, potatoes and butter keep for weeks, so what's
left of them at the end of a plan isn't counted as waste. Hard cheeses stay held (R8), so they aren't here."""

from dataclasses import replace
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Ingredient
from app.domain.enums import MealSlot
from app.planning.grocery_list import build_grocery
from app.planning.perishables import leftover_fate
from app.planning.rounding import round_batch
from app.planning.solver.model import SolvedBatch
from app.testing import factories as f

LONG_KEEPERS = {
    "onion-yellow": ("pantry", 28),
    "onion-red": ("pantry", 28),
    "garlic": ("pantry", 56),
    "potato-russet": ("pantry", 28),
    "butter-salted": ("fridge", 30),
    "butter-unsalted": ("fridge", 30),
}


def test_the_seed_gives_them_multi_week_shelf_lives(seeded_db):
    rows = {r.slug: r for r in seeded_db.scalars(select(Ingredient).where(Ingredient.slug.in_(LONG_KEEPERS)))}
    assert set(rows) == set(LONG_KEEPERS)
    for slug, (where, days) in LONG_KEEPERS.items():
        row = rows[slug]
        assert row.is_perishable and row.typical_location == where
        life = row.shelf_life_days_pantry if where == "pantry" else row.shelf_life_days_fridge
        assert life == days >= 14, slug  # outlasts this week and the next
    assert rows["butter-salted"].shelf_life_days_freezer == 180
    cheddar = seeded_db.scalars(select(Ingredient).where(Ingredient.slug == "cheddar")).one()
    assert "possible_beef" in cheddar.diet_tags and cheddar.shelf_life_days_fridge is None  # still held


def test_a_long_keeper_does_not_spoil_within_two_weeks_but_unknown_fresh_food_does():
    butter = f.ingredient(1, "butter", perishable=True, location="fridge", shelf_life_days_fridge=30)
    onion = f.ingredient(2, "onion", perishable=True, location="pantry", shelf_life_days_pantry=28)
    spinach = f.ingredient(3, "spinach", perishable=True, location="fridge")
    rice = f.ingredient(4, "rice", location="pantry")
    assert not butter.spoils_within(14) and not onion.spoils_within(14) and not rice.spoils_within(14)
    assert spinach.spoils_within(14)
    assert butter.spoils_within(31) and onion.shelf_life_days() == 28
    assert replace(onion, location="fridge").shelf_life_days() is None  # no fridge figure recorded


def test_leftover_butter_keeps_and_leftover_spinach_is_at_risk():
    c = f.constraints()
    butter = f.ingredient(1, "butter", perishable=True, location="fridge", shelf_life_days_fridge=30)
    assert leftover_fate(butter, c) == "keeps"
    assert leftover_fate(replace(butter, shelf_life_days_fridge=None), c) == "at_risk"


def test_a_long_keeper_remainder_is_not_a_perishable_remainder_for_absorption():
    ing = {
        1: f.food(
            1,
            "butter",
            717,
            perishable=True,
            location="fridge",
            offers=[f.offer(11, package=454, package_cents=499)],
        ),
        2: f.food(2, "rice", 360, offers=[f.offer(21, package=2000, package_cents=400)]),
    }
    ing[1] = replace(ing[1], shelf_life_days_fridge=30)
    recipe = f.recipe(30, "Buttered rice", [MealSlot.DINNER], [f.line(1, 40), f.line(2, 300)], ing, base=4)
    c = f.constraints()
    p = f.problem(c, [recipe], ing)
    batches = [round_batch(p, SolvedBatch(30, f.MONDAY, c.default_portion_size, Decimal(1), 4))]
    grocery = build_grocery(p.constraints, batches, p.ingredients)
    butter = next(i for i in grocery.items if i.ingredient_id == 1)
    assert butter.remainder and not butter.perishable  # the rest of the pound keeps; nothing to absorb
