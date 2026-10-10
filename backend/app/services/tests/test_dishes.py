"""Dish categories of the stored seed recipes (AC 6), computed from their stored lines and ingredient data,
match the pure classifier's expectations (domain/tests/test_dish_category.py)."""

from sqlalchemy import select

from app.db.models import Recipe
from app.domain.dish_category import DishCategory as C
from app.services.dishes import dish_categories

EXPECTED = {
    "Chicken over rice with garlic yogurt sauce": C.BOWL,
    "Air-fryer chicken over rice with broccoli": C.ROAST,
    "Sheet-pan chicken and peppers over rice": C.ROAST,
    "Everyday chicken curry gravy": C.CURRY,
    "Yogurt chicken gravy": C.CURRY,
    "Chicken and spinach gravy": C.CURRY,
    "Double chocolate protein pudding": C.DESSERT,
    "Chocolate protein chia pudding": C.DESSERT,
    "Egg, spinach and pepper breakfast wraps": C.WRAP,
    "Chocolate protein overnight oats": C.OATS,
}


def test_every_stored_seed_recipe_gets_its_expected_category(seeded_db):
    recipes = list(seeded_db.scalars(select(Recipe).where(Recipe.origin == "seed")))
    categories = dish_categories(seeded_db, [r.default_version_id for r in recipes])
    got = {r.title: categories[r.default_version_id] for r in recipes}
    assert got == EXPECTED


def test_no_versions_no_queries(seeded_db):
    assert dish_categories(seeded_db, []) == {}
