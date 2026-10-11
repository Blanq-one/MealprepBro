"""The solver's shortlist (decided at the 2b.4 approval): each meal keeps its best few candidates, preferring
ones that share ingredients; never-favored and disliked recipes come last; the same input always gives the
same shortlist."""

from decimal import Decimal

from app.domain.enums import MealSlot
from app.planning import shortlist as sl
from app.planning.problem import CandidateRecipe, IngredientPlan, PlanningProblem
from app.planning.shortlist import shortlist
from app.testing import factories as f

D = MealSlot.DINNER
CHICKEN, RICE, TOFU, PASTA, SALMON, LENTILS, OIL = range(1, 8)


def ingredients() -> dict[int, IngredientPlan]:
    def food(i: int, name: str, kcal: int, protein: int) -> IngredientPlan:
        return f.ingredient(i, name, per_100g={"energy_kcal": kcal, "protein_g": protein})

    return {
        CHICKEN: food(CHICKEN, "chicken", 150, 25),
        RICE: food(RICE, "rice", 360, 7),
        TOFU: food(TOFU, "tofu", 140, 15),
        PASTA: food(PASTA, "pasta", 370, 13),
        SALMON: food(SALMON, "salmon", 200, 20),
        LENTILS: food(LENTILS, "lentils", 350, 25),
        OIL: f.ingredient(OIL, "oil", unit="ml", per_100g={"energy_kcal": 880}, always_have=True),
    }


def dinner(
    vid: int, lines: list[tuple[int, int]], ing: dict[int, IngredientPlan], **kw: object
) -> CandidateRecipe:
    return f.recipe(vid, f"dinner {vid}", [D], [f.line(i, q) for i, q in lines], ing, **kw)  # type: ignore[arg-type]


def problem(candidates: list[CandidateRecipe], ing: dict[int, IngredientPlan]) -> PlanningProblem:
    return f.problem(f.constraints(slots={D: 650}), candidates, ing)


def test_a_small_library_is_left_whole():
    ing = ingredients()
    cands = [dinner(1, [(CHICKEN, 600), (RICE, 300)], ing), dinner(2, [(TOFU, 600), (RICE, 300)], ing)]
    p = problem(cands, ing)
    assert shortlist(p, 3) is p


def test_each_meal_keeps_its_best_few_and_prefers_shared_ingredients(monkeypatch):
    ing = ingredients()
    cands = [
        dinner(1, [(CHICKEN, 600), (RICE, 300)], ing),
        dinner(2, [(CHICKEN, 500), (RICE, 350)], ing),  # shares both of 1's ingredients
        dinner(3, [(SALMON, 550), (PASTA, 300)], ing),  # scores a bit better than 2, with two new ingredients
        dinner(4, [(LENTILS, 300), (PASTA, 300)], ing),
        dinner(5, [(TOFU, 400), (PASTA, 400)], ing),
    ]
    scores = {1: Decimal(2), 2: Decimal(1), 3: Decimal("1.2"), 4: Decimal("0.1"), 5: Decimal(0)}
    monkeypatch.setattr(sl, "score_pool", lambda pool, problem, kcal: scores)
    out = shortlist(problem(cands, ing), 2)
    assert [c.version_id for c in out.candidates] == [1, 2]  # 3's two new ingredients cost 0.3
    monkeypatch.setattr(sl, "W_NEW_INGREDIENT", Decimal(0))
    assert [c.version_id for c in shortlist(problem(cands, ing), 2).candidates] == [1, 3]


def test_the_same_input_always_gives_the_same_shortlist():
    ing = ingredients()
    cands = [
        dinner(1, [(CHICKEN, 600), (RICE, 300)], ing),
        dinner(2, [(CHICKEN, 500), (RICE, 350)], ing),
        dinner(3, [(SALMON, 550), (PASTA, 300)], ing),
        dinner(4, [(LENTILS, 300), (PASTA, 300)], ing),
        dinner(5, [(TOFU, 400), (PASTA, 400)], ing),
    ]
    first = sorted(c.version_id for c in shortlist(problem(cands, ing), 2).candidates)
    assert first == sorted(c.version_id for c in shortlist(problem(list(reversed(cands)), ing), 2).candidates)
    assert len(first) == 2


def test_favorites_are_kept_and_never_favored_or_disliked_recipes_come_last():
    ing = ingredients()
    cands = [
        dinner(1, [(CHICKEN, 600), (RICE, 300)], ing, never_favored=True),  # best on paper: a pork component
        dinner(2, [(CHICKEN, 590), (RICE, 300)], ing, disliked=True),
        dinner(3, [(TOFU, 500), (RICE, 300)], ing),
        dinner(4, [(PASTA, 300), (LENTILS, 200)], ing, favorite=True),
    ]
    out = shortlist(problem(cands, ing), 2)
    assert sorted(c.version_id for c in out.candidates) == [3, 4]
