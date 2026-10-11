"""The solver's shortlist (decided at the 2b.4 approval): each meal keeps its best few candidates, preferring
ones that share ingredients; never-favored and disliked recipes come last; the same input always gives the
same shortlist."""

from decimal import Decimal

from app.domain.enums import CalorieMode, MealSlot, PlanningMode, RecipeMood
from app.planning import shortlist as sl
from app.planning.problem import CandidateRecipe, IngredientPlan, InventoryLot, PlanningProblem
from app.planning.shortlist import shortlist
from app.planning.solver.model import SolverSolution
from app.planning.solver.solve import solve
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


def test_each_meal_always_keeps_its_quickest_recipe_and_one_its_strictest_day_allows(monkeypatch):
    """P3 (2b.3b approval): the first day of the week cooks every meal itself, so the shortlist always holds
    the quickest recipe for each meal, and the quickest one a simple cook day allows."""
    ing = ingredients()
    cands = [
        dinner(1, [(CHICKEN, 600), (RICE, 300)], ing, active=40, mood=RecipeMood.MEDIUM),
        dinner(2, [(CHICKEN, 500), (RICE, 350)], ing, active=35, mood=RecipeMood.MEDIUM),
        dinner(3, [(SALMON, 550), (PASTA, 300)], ing, active=30, mood=RecipeMood.MEDIUM),
        dinner(4, [(LENTILS, 300), (PASTA, 300)], ing, active=10, mood=RecipeMood.MEDIUM),  # quickest
        dinner(5, [(TOFU, 400), (PASTA, 400)], ing, active=25, mood=RecipeMood.SIMPLE),  # quickest simple
    ]
    scores = {1: Decimal(3), 2: Decimal(2), 3: Decimal(1), 4: Decimal(0), 5: Decimal(0)}
    monkeypatch.setattr(sl, "score_pool", lambda pool, problem, kcal: scores)
    medium_week = f.problem(f.constraints(slots={D: 650}), cands, ing)
    assert sorted(c.version_id for c in shortlist(medium_week, 3).candidates) == [1, 2, 4]
    with_simple = f.problem(f.constraints(slots={D: 650}, mood=RecipeMood.SIMPLE), cands, ing)
    assert sorted(c.version_id for c in shortlist(with_simple, 3).candidates) == [1, 4, 5]


# ---------------- with a money limit: the cheap options are always kept (D102 follow-up) ----------------
L = MealSlot.LUNCH
SALMON_FILLET, WHITE_RICE, DRY_LENTILS = 11, 12, 13


def money_week(budget_cents: int | None = None, *, pantry: bool = True, **kw: object) -> PlanningProblem:
    """18 salmon lunches that score well (protein per kcal, right on the meal's calories) but cost $9 a
    portion, and two that score worst: a cheap rice bowl and a lentil soup your pantry already covers (its
    lentils are dear per gram, so only its buy-today total is cheap)."""
    ing = {
        SALMON_FILLET: f.food(
            SALMON_FILLET, "salmon", 200, protein=25, offers=[f.offer(101, cents_per_unit="3")]
        ),
        WHITE_RICE: f.food(WHITE_RICE, "rice", 360, protein=7, offers=[f.offer(102, cents_per_unit="0.2")]),
        DRY_LENTILS: f.food(
            DRY_LENTILS,
            "lentils",
            360,
            protein=9,
            offers=[f.offer(103, cents_per_unit="5")],
            lots=[InventoryLot(1, DRY_LENTILS, Decimal(2000))] if pantry else [],
        ),
    }
    cands = [
        f.recipe(100 + i, f"Salmon bowl {i}", [L], [f.line(SALMON_FILLET, 1200 + 2 * i)], ing, active=10)
        for i in range(18)
    ]
    cands.append(f.recipe(200, "Rice bowl", [L], [f.line(WHITE_RICE, 640)], ing, active=20))
    cands.append(f.recipe(201, "Lentil soup", [L], [f.line(DRY_LENTILS, 640)], ing, active=20))
    c = f.constraints(
        days=3,
        slots={L: 600},
        cook_weekdays=range(7),
        calorie_mode=CalorieMode.STRICT_DAILY,
        budget_cents=budget_cents,
        **kw,  # type: ignore[arg-type]
    )
    if kw.get("mode") is PlanningMode.INVENTORY:
        assert c.purchase_limit_cents == 0
    return f.problem(c, cands, ing)


def test_without_a_money_limit_the_cheap_lunches_rank_below_the_top_6():
    kept = {c.title for c in shortlist(money_week(), 6).candidates}
    assert "Rice bowl" not in kept and "Lentil soup" not in kept
    assert len(kept) == 6


def test_a_budget_keeps_the_cheapest_recipe_so_the_only_plan_that_fits_is_found():
    # $5 for three lunches, nothing in the pantry: only the rice bowl fits ($0.32 a portion)
    p = money_week(budget_cents=500, pantry=False)
    for per_slot in (3, 6):
        assert "Rice bowl" in {c.title for c in shortlist(p, per_slot).candidates}
    result = solve(shortlist(p, 3), time_limit_s=30)
    assert isinstance(result, SolverSolution), result
    assert {result.batches[m.batch_index].version_id for m in result.meals} == {200}


def test_a_top_up_keeps_the_recipe_cheapest_to_buy_today():
    """Inventory mode with no top-up: only the lentil soup, which the pantry covers, can be cooked; per
    portion at shop prices it's the dearest recipe of all, so only its buy-today total ($0) keeps it."""
    p = money_week(mode=PlanningMode.INVENTORY, topup_cents=0)
    kept = {c.title for c in shortlist(p, 3).candidates}
    assert {"Rice bowl", "Lentil soup"} <= kept  # cheapest per portion, cheapest to buy today
    result = solve(shortlist(p, 3), time_limit_s=30)
    assert isinstance(result, SolverSolution), result
    assert {result.batches[m.batch_index].version_id for m in result.meals} == {201}
