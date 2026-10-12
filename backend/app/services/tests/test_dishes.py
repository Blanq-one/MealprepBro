"""Dish categories of the stored seed recipes (AC 6), computed from their stored lines and ingredient data,
match the pure classifier's expectations (domain/tests/test_dish_category.py)."""

from sqlalchemy import select

from app.db.models import Recipe, RecipeVersion
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
    # the 37 drafts of the step 2b.4 approval (M13)
    "Masala egg scramble with tortillas": C.EGGS,
    "Chicken sausage and egg breakfast burritos": C.WRAP,
    "Peanut butter banana overnight oats": C.OATS,
    "Egg and veggie muffin cups": C.EGGS,
    "Shakshuka with warm tortillas": C.EGGS,
    "Turkey and sweet potato breakfast hash": C.OTHER,
    "Egg kathi rolls with green chutney": C.EGGS,
    "Chicken tikka rice bowls": C.BOWL,
    "Yogurt chicken salad wraps": C.WRAP,
    "Chicken and black bean burrito bowls": C.BOWL,
    "Tuna and chickpea salad bowls": C.SALAD,
    "Egg fried rice with peas and carrots": C.BOWL,
    "Dal tadka with rice": C.CURRY,
    "Chicken shawarma pitas with garlic yogurt": C.SANDWICH,
    "Ground turkey tacos": C.WRAP,
    "Butter chicken with rice": C.CURRY,
    "Chicken korma with tortillas": C.CURRY,
    "Chicken chana masala with rice": C.CURRY,
    "Tandoori-style drumsticks with rice and raita": C.BOWL,
    "Sheet-pan bone-in thighs with potatoes and green beans": C.ROAST,
    "Lemon garlic salmon with rice and broccoli": C.BOWL,
    "Coconut shrimp curry with rice": C.CURRY,
    "Chicken keema with peas and tortillas": C.CURRY,
    "Whole roast chicken with root vegetables": C.ROAST,
    "Chicken, broccoli and pepper stir-fry": C.BOWL,
    "Air-fryer chicken wings with sweet potato wedges": C.ROAST,
    "Roast bone-in chicken breasts with quinoa and asparagus": C.ROAST,
    "Masala roasted chickpeas": C.SNACK,
    "Garlic yogurt cucumber dip with pita": C.SNACK,
    "Spiced egg chaat": C.SNACK,
    "Air-fryer chicken tikka bites": C.SNACK,
    "Chili-lime edamame": C.SNACK,
    "Chocolate peanut butter protein yogurt bowl": C.DESSERT,
    "Strawberry protein yogurt parfaits": C.DESSERT,
    "Chocolate protein mug cakes": C.DESSERT,
    "Mango lassi smoothie": C.DRINK,
    "Chocolate protein mousse with strawberries": C.DESSERT,
}


def test_every_stored_seed_recipe_gets_its_expected_category(seeded_db):
    recipes = [
        r
        for r in seeded_db.scalars(select(Recipe).where(Recipe.origin == "seed"))
        if seeded_db.get(RecipeVersion, r.default_version_id).kind == "dish"  # not 2b.10's items and meals
    ]
    categories = dish_categories(seeded_db, [r.default_version_id for r in recipes])
    got = {r.title: categories[r.default_version_id] for r in recipes}
    assert got == EXPECTED


def test_no_versions_no_queries(seeded_db):
    assert dish_categories(seeded_db, []) == {}
