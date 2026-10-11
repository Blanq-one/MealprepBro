"""Freezes well (H5; 2b.5 deliverable 9, AC 15): every seed has its reviewed value (rice dishes and curry
gravies yes; yogurt sauces and fresh salads no, or yes with a note to freeze the base and add the fresh part
later), an idea without the field fails the idea checks, and portions past the fridge window only come from
recipes that freeze well, in the solver and in the validator."""

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.cook.tests.conftest import idea
from app.domain.enums import MealSlot
from app.planning.ideas import salvage_ideas
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import PlanningProblem
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverSolution, batch_plan
from app.schemas.llm_recipe import RecipeIdea
from app.seed.files import load_seed_files
from app.testing import factories as f

# title -> freezes well (the step 2b.5 review)
REVIEWED = {
    "Chicken over rice with garlic yogurt sauce": True,
    "Air-fryer chicken over rice with broccoli": True,
    "Sheet-pan chicken and peppers over rice": True,
    "Everyday chicken curry gravy": True,
    "Yogurt chicken gravy": True,
    "Chicken and spinach gravy": True,
    "Double chocolate protein pudding": False,
    "Chocolate protein chia pudding": False,
    "Egg, spinach and pepper breakfast wraps": True,
    "Chocolate protein overnight oats": False,
    "Masala egg scramble with tortillas": False,
    "Chicken sausage and egg breakfast burritos": True,
    "Peanut butter banana overnight oats": False,
    "Egg and veggie muffin cups": True,
    "Shakshuka with warm tortillas": False,
    "Turkey and sweet potato breakfast hash": True,
    "Egg kathi rolls with green chutney": False,
    "Chicken tikka rice bowls": True,
    "Yogurt chicken salad wraps": False,
    "Chicken and black bean burrito bowls": True,
    "Tuna and chickpea salad bowls": False,
    "Egg fried rice with peas and carrots": True,
    "Dal tadka with rice": True,
    "Chicken shawarma pitas with garlic yogurt": True,
    "Ground turkey tacos": True,
    "Butter chicken with rice": True,
    "Chicken korma with tortillas": True,
    "Chicken chana masala with rice": True,
    "Tandoori-style drumsticks with rice and raita": True,
    "Sheet-pan bone-in thighs with potatoes and green beans": True,
    "Lemon garlic salmon with rice and broccoli": False,
    "Coconut shrimp curry with rice": True,
    "Chicken keema with peas and tortillas": True,
    "Whole roast chicken with root vegetables": True,
    "Chicken, broccoli and pepper stir-fry": True,
    "Air-fryer chicken wings with sweet potato wedges": True,
    "Roast bone-in chicken breasts with quinoa and asparagus": True,
    "Masala roasted chickpeas": False,
    "Garlic yogurt cucumber dip with pita": False,
    "Spiced egg chaat": False,
    "Air-fryer chicken tikka bites": True,
    "Chili-lime edamame": False,
    "Chocolate peanut butter protein yogurt bowl": False,
    "Strawberry protein yogurt parfaits": False,
    "Chocolate protein mug cakes": False,
    "Mango lassi smoothie": False,
    "Chocolate protein mousse with strawberries": False,
}


def test_every_seed_has_its_reviewed_value():
    seeds = {r.title: r for _, r in load_seed_files().recipes}
    assert set(seeds) == set(REVIEWED)
    assert {t: r.freezer_friendly for t, r in seeds.items()} == REVIEWED


def test_yogurt_sauces_and_fresh_salads_say_to_freeze_the_base():
    seeds = {r.title: r for _, r in load_seed_files().recipes}
    assert seeds["Chicken over rice with garlic yogurt sauce"].freeze_note == (
        "Freeze the chicken and rice; make the garlic yogurt sauce and the salad fresh."
    )
    for title in (
        "Tandoori-style drumsticks with rice and raita",
        "Chicken shawarma pitas with garlic yogurt",
    ):
        note = seeds[title].freeze_note
        assert note is not None and "fresh" in note
    assert all(r.freezer_friendly for r in seeds.values() if r.freeze_note is not None)


def test_an_idea_without_freezes_well_fails_the_idea_checks():
    good = idea("Chicken rice bowl")
    missing = {k: v for k, v in idea("Rice bowl without the field").items() if k != "freezer_friendly"}
    with pytest.raises(ValidationError, match="freezer_friendly"):
        RecipeIdea.model_validate(missing)
    kept = salvage_ideas({"ideas": [good, missing]})
    assert kept is not None and [i.title for i in kept.ideas] == ["Chicken rice bowl"]
    assert kept.ideas[0].freezer_friendly is True


def week_cooked_monday(freezes: bool) -> PlanningProblem:
    ing = {1: f.food(1, "chicken", 120, protein=22, offers=[f.offer(1, cents_per_unit="1")])}
    recipe = f.recipe(10, "Curry", [MealSlot.DINNER], [f.line(1, 450)], ing, base=1, freezer=freezes)
    c = f.constraints(days=6, slots={MealSlot.DINNER: 540}, cook_weekdays=(0,))
    return f.problem(c, [recipe], ing)


def test_the_solver_offers_portions_past_the_window_only_from_recipes_that_freeze_well():
    def latest(p: PlanningProblem) -> int:
        return max((e - f.MONDAY).days for b in batch_plan(p) for e, _ in b.targets)

    assert latest(week_cooked_monday(freezes=True)) == 5
    assert latest(week_cooked_monday(freezes=False)) == 3  # the fridge window


def test_the_validator_checks_each_portion_past_the_window_and_frozen_extras():
    p = week_cooked_monday(freezes=False)
    size = p.constraints.default_portion_size
    raw = SolverSolution(
        "optimal",
        0.0,
        (SolvedBatch(10, f.MONDAY, size, Decimal(1), 7, portions_to_freeze=1),),
        tuple(
            SolvedMeal(f.MONDAY + timedelta(days=i), MealSlot.DINNER, 0, from_freezer=i > 3) for i in range(6)
        ),
        {},
        frozenset({f.PRIMARY}),
        0,
    )
    codes = [e.code for e in validate_plan(build_rounded_plan(p, raw, absorb=False), f.reference(p)).errors]
    assert codes.count("FREEZER_NOT_FRIENDLY") == 3  # Fri and Sat dinners, and the frozen extra
    assert codes.count("FRIDGE_WINDOW") == 2
