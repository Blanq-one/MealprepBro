"""The weekly MILP on small synthetic weeks (no database)."""

import random
import time
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.config import get_settings
from app.domain.enums import CalorieMode, Equipment, MealSlot, NutritionPriority, PlanningMode, RecipeMood
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import ExcludedRecipe, InventoryLot
from app.planning.solver import model
from app.planning.solver.model import EmptyCandidatePoolError, SolverInfeasible, SolverSolution
from app.planning.solver.solve import solve
from app.schemas.constraints import ResolvedFrequencyCap
from app.testing import factories as f

MON = f.MONDAY
SUN = MON - timedelta(days=1)
B, L, D, P = MealSlot.BREAKFAST, MealSlot.LUNCH, MealSlot.DINNER, MealSlot.PROTEIN_DESSERT
LB = Decimal("453.59237")
PORK_CAP_LABEL = "Pork as a meal component"


@pytest.fixture(autouse=True)
def no_margins(monkeypatch, request):
    """These synthetic weeks test the solver's exact math, so the rounding margin inside its calorie limits is
    off (test_rounding_margin_keeps_room_inside_the_limits covers the margin itself)."""
    if "with_margins" not in request.keywords:
        monkeypatch.setattr(model, "ROUNDING_MARGIN_DAY_KCAL", 0)
        monkeypatch.setattr(model, "ROUNDING_MARGIN_WEEK_KCAL", 0)
        monkeypatch.setattr(model, "ROUNDING_MARGIN_DAY_PROTEIN_G", 0)
        monkeypatch.setattr(model, "ROUNDING_MARGIN_WEEK_PROTEIN_G", 0)


def ok(result) -> SolverSolution:
    assert isinstance(result, SolverSolution), getattr(result, "diagnostics", result)
    return result


def titles(p, s: SolverSolution) -> list[str]:
    return [p.candidate(s.batches[m.batch_index].version_id).title for m in s.meals]


def base_ingredients():
    return {
        1: f.food(
            1,
            "chicken",
            120,
            protein=22,
            perishable=True,
            offers=[
                f.offer(11, package=3 * LB, package_cents=1347),
                f.offer(12, f.SECONDARY, package=3 * LB, package_cents=1047),
            ],
        ),
        2: f.food(2, "rice", 360, carbs=80, offers=[f.offer(21, package=2268, package_cents=499)]),
        3: f.food(3, "eggs", 143, protein=12, offers=[f.offer(31, package=600, package_cents=329)]),
        4: f.food(4, "pudding mix", 100, protein=15, offers=[f.offer(41, cents_per_unit="0.5")]),
    }


def mains(ing, n=6, freezer=False):
    out = []
    for i in range(n):
        out.append(
            f.recipe(
                100 + i,
                f"Main {i}",
                [L, D],
                [f.line(1, 700 + 20 * i), f.line(2, 330)],
                ing,
                base=4,
                active=15,
                freezer=freezer,
            )
        )
    return out


# ---------------- schedule ----------------
def test_no_batches_on_tue_or_fri_and_leftovers_stay_in_the_fridge_window():
    ing = base_ingredients()
    c = f.constraints(week_start=SUN, slots={L: 560, D: 600}, cook_minutes=45)
    p = f.problem(c, mains(ing), ing)
    s = ok(solve(p, time_limit_s=30))
    cook_days = {b.cook_on.weekday() for b in s.batches}
    assert not cook_days & {1, 4}  # Tuesday, Friday
    for meal in s.meals:
        batch = s.batches[meal.batch_index]
        age = (meal.eat_on - batch.cook_on).days
        assert 0 <= age <= c.leftover_fridge_days
        assert not meal.from_freezer
        if meal.eat_on.weekday() == 1:  # Tuesday lunch/dinner from Sunday or Monday's cooking
            assert batch.cook_on in (SUN, MON)


def test_freezer_extends_only_freezer_friendly_recipes():
    ing = base_ingredients()
    c = f.constraints(slots={D: 520}, cook_weekdays=(0,), cook_minutes=45)  # only Monday is a cook day
    p = f.problem(c, mains(ing, n=2, freezer=True), ing)
    s = ok(solve(p, time_limit_s=30))
    for meal in s.meals:
        age = (meal.eat_on - s.batches[meal.batch_index].cook_on).days
        assert meal.from_freezer == (age > 3)
    p_fresh_only = f.problem(c, mains(ing, n=2, freezer=False), ing)
    assert isinstance(solve(p_fresh_only, time_limit_s=30), SolverInfeasible)  # Fri–Sun unreachable


# ---------------- calories ----------------
def one_slot_week(kcals, mode=CalorieMode.WEEKLY, days=3, target=1800, nudge=0.0):
    ing = {
        i + 1: f.food(i + 1, f"food {i}", 100, protein=10, offers=[f.offer(i + 1, cents_per_unit="0.1")])
        for i in range(len(kcals))
    }
    recipes = [f.recipe(10 + i, f"R{k}", [D], [f.line(i + 1, k)], ing, base=1) for i, k in enumerate(kcals)]
    c = f.constraints(
        days=days,
        slots={D: target},
        cook_weekdays=range(7),
        calorie_mode=mode,
        nudge_pct=nudge,
        max_portions=7,
    )
    return f.problem(c, recipes, ing)


def test_weekly_mode_allows_t_plus_140():
    p = one_slot_week([1720, 1940])
    s = ok(solve(p))
    assert max(s.day_kcal.values()) == 1940
    assert sum(s.day_kcal.values()) <= 5400


def test_weekly_mode_rejects_t_plus_160():
    assert isinstance(solve(one_slot_week([1720, 1960])), SolverInfeasible)


def test_strict_mode_keeps_every_day_at_or_under_target():
    p = one_slot_week([1700, 1790, 1820], mode=CalorieMode.STRICT_DAILY)
    s = ok(solve(p))
    assert all(1710 <= k <= 1800 for k in s.day_kcal.values())


@pytest.mark.with_margins
def test_rounding_margin_keeps_room_inside_the_limits(monkeypatch):
    p = one_slot_week([1720, 1948])  # needs one 1,948 kcal day; the band allows up to 1,950
    assert isinstance(solve(p), SolverInfeasible)  # but the solver keeps 5 kcal for rounding
    monkeypatch.setattr(model, "ROUNDING_MARGIN_DAY_KCAL", 0)
    monkeypatch.setattr(model, "ROUNDING_MARGIN_WEEK_KCAL", 0)
    assert isinstance(solve(p), SolverSolution)


def test_the_week_never_exceeds_its_target():
    for mode in (CalorieMode.WEEKLY, CalorieMode.STRICT_DAILY):
        ing = base_ingredients()
        c = f.constraints(slots={L: 560, D: 600}, calorie_mode=mode, daily_under_pct=8)
        s = ok(solve(f.problem(c, mains(ing), ing), time_limit_s=30))
        assert sum(s.day_kcal.values()) <= c.weekly_kcal_target


# ---------------- priorities and the protein target ----------------
def bowls(lean_cents: str = "0.5", starch_cents: str = "0.5"):
    """One portion = 400 g = 600 kcal: the lean bowl has 120 g protein, the starch bowl 12 g."""
    ing = {
        1: f.food(1, "lean", 150, protein=30, carbs=0, offers=[f.offer(1, cents_per_unit=lean_cents)]),
        2: f.food(2, "starch", 150, protein=3, carbs=30, offers=[f.offer(2, cents_per_unit=starch_cents)]),
    }
    recipes = [
        f.recipe(1, "Lean bowl", [D], [f.line(1, 1600)], ing),
        f.recipe(2, "Starch bowl", [D], [f.line(2, 1600)], ing),
    ]
    return ing, recipes


def test_carb_priority_still_scores_carbs():
    ing, recipes = bowls()
    c = f.constraints(
        days=2, slots={D: 600}, cook_weekdays=(0,), priority=NutritionPriority.CARB, nudge_pct=0
    )
    s = ok(solve(f.problem(c, recipes, ing)))
    assert set(titles(f.problem(c, recipes, ing), s)) == {"Starch bowl"}


def test_protein_above_the_target_earns_nothing():
    """Protein focus with no binding target: the cheaper, low-protein bowl wins (no reward for protein)."""
    ing, recipes = bowls(lean_cents="1.0", starch_cents="0.25")
    for target in (0, 12):
        c = f.constraints(days=2, slots={D: 600}, cook_weekdays=(0,), nudge_pct=0, protein_g=target)
        s = ok(solve(f.problem(c, recipes, ing)))
        assert set(titles(f.problem(c, recipes, ing), s)) == {"Starch bowl"}


@pytest.mark.parametrize(
    ("mode", "lean_meals"),
    [(CalorieMode.STRICT_DAILY, 2), (CalorieMode.WEEKLY, 1)],  # weekly: one 120 g day covers 2 × 60 g
)
def test_the_protein_target_is_a_floor_per_calorie_mode(mode, lean_meals):
    ing, recipes = bowls(lean_cents="1.0", starch_cents="0.25")
    c = f.constraints(
        days=2, slots={D: 600}, cook_weekdays=(0,), nudge_pct=0, protein_g=60, calorie_mode=mode
    )
    p = f.problem(c, recipes, ing)
    s = ok(solve(p))
    assert titles(p, s).count("Lean bowl") == lean_meals  # never more lean than the floor needs
    plan = build_rounded_plan(p, s, absorb=False)
    report = validate_plan(plan, f.reference(p))
    assert report.ok, report.errors
    if mode is CalorieMode.STRICT_DAILY:
        assert all(g >= 60 for g in plan.totals.day_protein_g.values())
    else:
        assert plan.totals.week_protein_g >= 120


@pytest.mark.parametrize("mode", [CalorieMode.STRICT_DAILY, CalorieMode.WEEKLY])
def test_a_protein_target_no_recipe_can_reach_is_explained(mode):
    ing, recipes = bowls()
    c = f.constraints(
        days=2, slots={D: 600}, cook_weekdays=(0,), nudge_pct=0, protein_g=60, calorie_mode=mode
    )
    result = solve(f.problem(c, [recipes[1]], ing))  # the starch bowl only: 12 g a day
    assert isinstance(result, SolverInfeasible)
    short = [d for d in result.diagnostics if d.code == "PROTEIN_SHORT"]
    if mode is CalorieMode.STRICT_DAILY:
        assert len(short) == 2 and short[0].amount == 48
        assert "can reach only about 12 g protein; your target is 60 g (short by 48 g)" in short[0].message
    else:
        assert len(short) == 1 and short[0].amount == 96
        assert "The week can reach only about 24 g protein; your target is 120 g" in short[0].message


# ---------------- portions ----------------
def test_odd_portion_counts():
    ing = base_ingredients()
    dessert = f.recipe(7, "Pudding", [P], [f.line(4, 400)], ing, base=2, freezer=True)
    c = f.constraints(slots={P: 200}, cook_weekdays=(0,), nudge_pct=0)
    s = ok(solve(f.problem(c, [dessert], ing)))
    assert [b.portions for b in s.batches] == [7]  # desserts are exempt from the 5-portion meal cap
    c3 = f.constraints(days=3, slots={P: 200}, cook_weekdays=(0,), nudge_pct=0)
    assert [b.portions for b in ok(solve(f.problem(c3, [dessert], ing))).batches] == [3]
    c5 = f.constraints(days=5, slots={D: 510}, cook_weekdays=(0,), fridge_days=4, nudge_pct=0)
    s5 = ok(solve(f.problem(c5, mains(ing, n=1), ing)))
    assert [b.portions for b in s5.batches] == [5]


def test_portion_variants_help_hit_a_tight_day():
    strict = dict(mode=CalorieMode.STRICT_DAILY, days=2, target=1000)
    assert isinstance(solve(one_slot_week([900], nudge=0.0, **strict)), SolverInfeasible)  # 900 < 950 floor
    s = ok(solve(one_slot_week([900], nudge=10.0, **strict)))
    assert all(b.nudge > 1 for b in s.batches)
    assert all(950 <= k <= 1000 for k in s.day_kcal.values())


# ---------------- packages, stores, inventory ----------------
def store_week(primary_cents, secondary_cents, threshold=500):
    ing = {
        1: f.food(
            1,
            "chicken",
            120,
            protein=22,
            perishable=True,
            offers=[
                f.offer(11, f.PRIMARY, package=3 * LB, package_cents=primary_cents),
                f.offer(12, f.SECONDARY, package=3 * LB, package_cents=secondary_cents),
            ],
        ),
    }
    rec = f.recipe(1, "Chicken", [D], [f.line(1, 1360)], ing, base=4)
    c = f.constraints(
        days=4, slots={D: 408}, cook_weekdays=(0,), nudge_pct=0, threshold_cents=threshold, band=200
    )
    return f.problem(c, [rec], ing)


@pytest.mark.parametrize(
    ("primary", "secondary", "threshold", "split"),
    [(1540, 1000, 500, True), (1490, 1000, 500, False), (1490, 1000, 300, True)],
)
def test_price_rite_only_when_it_saves_the_threshold(primary, secondary, threshold, split):
    p = store_week(primary, secondary, threshold)
    s = ok(solve(p))
    assert (f.SECONDARY in s.stores_used) is split
    plan = build_rounded_plan(p, s, absorb=False)
    (chicken,) = [i for i in plan.grocery.items if i.name == "chicken"]
    assert chicken.store_id == (f.SECONDARY if split else f.PRIMARY)
    assert plan.grocery.savings_cents == primary - secondary


def test_inventory_that_covers_rice_buys_none():
    ing = base_ingredients()
    ing[2] = replace(ing[2], lots=(InventoryLot(9, 2, Decimal(3000)),))
    c = f.constraints(days=3, slots={D: 520}, cook_weekdays=(0,))
    p = f.problem(c, mains(ing, n=1), ing)
    plan = build_rounded_plan(p, ok(solve(p)), absorb=False)
    (rice,) = [i for i in plan.grocery.items if i.name == "rice"]
    assert rice.kind == "from_inventory" and rice.cost_cents is None


def twin_week(extra_ing, lots_for=None, lot=None):
    ing = base_ingredients()
    ing.update(extra_ing)
    if lots_for is not None:
        ing[lots_for] = replace(ing[lots_for], lots=(lot,))
    return ing


def test_expiring_spinach_wins_a_tie():
    greens = {
        5: f.food(5, "spinach", 23, protein=3, perishable=True, offers=[f.offer(51, cents_per_unit="0.8")]),
        6: f.food(6, "kale", 23, protein=3, perishable=True, offers=[f.offer(61, cents_per_unit="0.8")]),
    }
    ing = twin_week(greens, 5, InventoryLot(5, 5, Decimal(300), expires_on=MON + timedelta(days=2)))
    a = f.recipe(1, "Kale chicken", [D], [f.line(1, 700), f.line(6, 300)], ing)
    b = f.recipe(2, "Spinach chicken", [D], [f.line(1, 700), f.line(5, 300)], ing)
    c = f.constraints(days=3, slots={D: 230}, cook_weekdays=(0,), nudge_pct=0, band=200)
    p = f.problem(c, [a, b], ing)
    assert set(titles(p, ok(solve(p)))) == {"Spinach chicken"}


def test_open_package_of_chicken_is_used_first():
    thighs = {
        7: f.food(
            7,
            "chicken thigh",
            120,
            protein=22,
            perishable=True,
            offers=[f.offer(71, package=3 * LB, package_cents=1347)],
        )
    }
    ing = twin_week(thighs, 7, InventoryLot(7, 7, Decimal(600), opened_on=MON - timedelta(days=1)))
    a = f.recipe(1, "Breast bowl", [D], [f.line(1, 700), f.line(2, 300)], ing)
    b = f.recipe(2, "Thigh bowl", [D], [f.line(7, 700), f.line(2, 300)], ing)
    c = f.constraints(days=3, slots={D: 480}, cook_weekdays=(0,), nudge_pct=0)
    p = f.problem(c, [a, b], ing)
    assert set(titles(p, ok(solve(p)))) == {"Thigh bowl"}


# ---------------- frequency caps (pork components) ----------------
def pork_ingredients():
    ing = base_ingredients()
    ing[20] = f.food(20, "pork sausage", 300, protein=25, offers=[f.offer(201, cents_per_unit="0.3")])
    ing[21] = f.food(21, "bacon", 400, protein=30, offers=[f.offer(211, cents_per_unit="0.3")])
    ing[22] = f.ingredient(
        22,
        "flour tortilla (lard)",
        unit="count",
        piece_grams="37",
        per_100g={"energy_kcal": 297, "protein_g": 8, "carbohydrate_g": 51, "fat_g": 5},
        offers=[f.offer(221, package=20, package_cents=199)],
    )
    ing[23] = f.food(23, "pork gelatin", 335, protein=85, offers=[f.offer(231, cents_per_unit="2")])
    ing[24] = f.food(24, "salmon", 200, protein=20, offers=[f.offer(241, cents_per_unit="2")])
    return ing


def pork_cap(max_meals: int, members=(20, 21)) -> ResolvedFrequencyCap:
    return ResolvedFrequencyCap(
        label=PORK_CAP_LABEL, member_ingredient_ids=frozenset(members), max_meals_per_week=max_meals
    )


def pork_meals(p, s) -> int:
    members = {20, 21}
    return sum(
        1 for m in s.meals if p.candidate(s.batches[m.batch_index].version_id).ingredient_ids & members
    )


def sausage_recipes(ing, n=3):
    return [
        f.recipe(
            300 + i,
            f"Sausage {i}",
            [L, D],
            [f.line(20, 650 + 10 * i), f.line(2, 280)],
            ing,
            active=15,
            freezer=True,
            never_favored=True,
        )
        for i in range(n)
    ]


def test_three_best_sausage_recipes_still_give_at_most_one_pork_meal():
    ing = pork_ingredients()
    c = f.constraints(slots={L: 560, D: 600}, caps=[pork_cap(1)])
    p = f.problem(c, mains(ing, n=4) + sausage_recipes(ing), ing)
    s = ok(solve(p, time_limit_s=30))
    assert pork_meals(p, s) <= 1
    for batch_index, batch in enumerate(s.batches):  # a sausage batch feeds at most one meal this week
        if p.candidate(batch.version_id).never_favored:
            assert sum(1 for m in s.meals if m.batch_index == batch_index) <= 1


@settings(max_examples=6, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(cap=st.integers(min_value=0, max_value=3), seed=st.integers(min_value=0, max_value=10_000))
def test_pork_meals_never_exceed_the_cap(cap, seed):
    rnd = random.Random(seed)
    ing = pork_ingredients()
    chicken = [
        f.recipe(
            100 + i,
            f"Main {i}",
            [D],
            [f.line(1, rnd.randint(650, 800)), f.line(2, rnd.randint(250, 350))],
            ing,
            active=rnd.choice([10, 15, 20]),
        )
        for i in range(rnd.randint(2, 3))
    ]
    pork = [
        f.recipe(
            300 + i,
            f"Pork {i}",
            [D],
            [f.line(rnd.choice([20, 21]), rnd.randint(500, 700)), f.line(2, 280)],
            ing,
            active=10,
            never_favored=True,
        )
        for i in range(rnd.randint(1, 3))
    ]
    c = f.constraints(
        days=4, slots={D: 700}, cook_weekdays=(0, 2), caps=[pork_cap(cap)], band=400, weekly_under_pct=25
    )
    p = f.problem(c, chicken + pork, ing)
    result = solve(p, time_limit_s=20)
    if isinstance(result, SolverSolution):
        assert pork_meals(p, result) <= cap


def test_cap_zero_keeps_trace_pork_recipes():
    ing = pork_ingredients()
    wrap = f.recipe(400, "Chicken wraps", [D], [f.line(1, 500), f.line(22, 8, "count")], ing)
    jelly = f.recipe(
        401, "Pork-gelatin panna cotta", [P], [f.line(23, 60), f.line(4, 300)], ing, base=2, freezer=True
    )
    c = f.constraints(days=3, slots={D: 400, P: 250}, cook_weekdays=(0,), caps=[pork_cap(0)], band=250)
    p = f.problem(c, [wrap, jelly, *sausage_recipes(ing, 2)], ing)
    s = ok(solve(p))
    assert pork_meals(p, s) == 0
    assert {"Chicken wraps", "Pork-gelatin panna cotta"} <= set(titles(p, s))


def test_a_better_pork_recipe_is_never_favored():
    ing = pork_ingredients()
    lot = InventoryLot(3, 21, Decimal(600), opened_on=MON - timedelta(days=1))  # an open package of bacon
    ing[21] = f.food(21, "bacon", 150, protein=35, offers=[f.offer(211, cents_per_unit="0.3")], lots=[lot])
    chicken = f.recipe(1, "Chicken bowl", [D], [f.line(1, 800), f.line(2, 280)], ing)
    bacon = f.recipe(
        2, "Bacon bowl", [D], [f.line(21, 240), f.line(1, 500), f.line(2, 280)], ing, never_favored=True
    )
    assert bacon.kcal == chicken.kcal  # otherwise equal...
    assert bacon.per_portion["protein_g"] > chicken.per_portion["protein_g"]  # ...but more protein
    assert bacon.cost_cents_per_portion < chicken.cost_cents_per_portion  # ...and cheaper
    c = f.constraints(days=3, slots={D: 492}, cook_weekdays=(0,), caps=[pork_cap(1)], band=250)
    p = f.problem(c, [chicken, bacon], ing)
    assert set(titles(p, ok(solve(p)))) == {"Chicken bowl"}


def test_ingredient_target_cap_is_honored():
    ing = pork_ingredients()
    salmon = f.recipe(500, "Salmon rice", [D], [f.line(24, 700), f.line(2, 250)], ing, freezer=True)
    rice = f.recipe(501, "Chicken rice", [D], [f.line(1, 700), f.line(2, 330)], ing, freezer=True)
    cap = ResolvedFrequencyCap(label="Salmon", member_ingredient_ids=frozenset({24}), max_meals_per_week=2)
    c = f.constraints(slots={D: 560}, caps=[cap], priority=NutritionPriority.PROTEIN)
    p = f.problem(c, [salmon, rice], ing)
    s = ok(solve(p, time_limit_s=30))
    assert titles(p, s).count("Salmon rice") <= 2


# ---------------- planning modes: shop (optional budget) and inventory (optional top-up) ----------------
def three_dinners(**kwargs):
    ing = base_ingredients()
    c = f.constraints(days=3, slots={D: 520}, cook_weekdays=(0,), store_ids=(f.PRIMARY,), **kwargs)
    return ing, c


def stock(ing, chicken=None, rice=None):
    """Inventory lots (planning units): 3 dinners need about 540 g chicken and 250 g rice."""
    out = dict(ing)
    if chicken is not None:
        out[1] = replace(ing[1], lots=(InventoryLot(901, 1, Decimal(chicken)),))
    if rice is not None:
        out[2] = replace(ing[2], lots=(InventoryLot(902, 2, Decimal(rice)),))
    return out


def test_shop_without_a_budget_minimizes_and_reports_the_cash():
    ing, c = three_dinners()
    p = f.problem(c, mains(ing, n=2), ing)
    plan = build_rounded_plan(p, ok(solve(p)), absorb=False)
    report = validate_plan(plan, f.reference(p))
    assert report.ok, report.errors
    assert plan.costs.cash_cents == plan.grocery.total_cents == 1347 + 499  # one chicken pack, one rice bag
    assert plan.costs.eaten_cents < plan.costs.cash_cents  # the rest of the packs carries into inventory


def test_shop_budget_too_low_is_infeasible_and_says_what_the_plan_would_cost():
    ing, c = three_dinners(budget_cents=500)
    result = solve(f.problem(c, mains(ing, n=1), ing))
    assert isinstance(result, SolverInfeasible)
    (short,) = [d for d in result.diagnostics if d.code == "BUDGET_SHORT"]
    assert short.amount == 1347 + 499 - 500  # whole packages: the cheapest plan is $18.46
    assert "costs about $18.46 in regular groceries, $13.46 over your budget of $5.00" in short.message
    items = " | ".join(short.items)  # what it would buy, apart from the message (2b.4 approval, B)
    assert "chicken about" in items and "rice about" in items


def test_when_only_the_money_is_short_the_diagnosis_is_only_about_money():
    """Lunch and dinner from Monday's 45 minutes. Two cheap 30-minute recipes are the cheapest way out if
    every limit may give (15 minutes over), but chicken + beans fits every limit except the $5 budget, so
    the report is about money only: what that plan costs, not a time shortfall."""
    ing = {
        1: f.food(1, "chicken", 120, offers=[f.offer(11, cents_per_unit="5")]),
        2: f.food(2, "beans", 120, offers=[f.offer(21, cents_per_unit="0.05")]),
        3: f.food(3, "lentils", 120, offers=[f.offer(31, cents_per_unit="0.05")]),
    }
    recipes = [
        f.recipe(1, "Quick chicken", [L, D], [f.line(1, 1700)], ing, active=15),
        f.recipe(2, "Slow beans", [L, D], [f.line(2, 1700)], ing, active=30),
        f.recipe(3, "Slow lentils", [L, D], [f.line(3, 1700)], ing, active=30),
    ]
    c = f.constraints(
        days=2,
        slots={L: 510, D: 510},
        cook_weekdays=(0,),
        store_ids=(f.PRIMARY,),
        budget_cents=500,
        nudge_pct=0,
    )
    result = solve(f.problem(c, recipes, ing))
    assert isinstance(result, SolverInfeasible)
    assert [d.code for d in result.diagnostics] == ["BUDGET_SHORT"]
    assert "chicken about 850 g ($42.50)" in result.diagnostics[0].items


def test_shop_mode_uses_inventory_first():
    ing, c = three_dinners(budget_cents=1400)  # enough for chicken, not for chicken and rice
    ing = stock(ing, rice=1000)
    p = f.problem(c, mains(ing, n=1), ing)
    plan = build_rounded_plan(p, ok(solve(p)), absorb=False)
    assert validate_plan(plan, f.reference(p)).ok
    bought = {item.name for item in plan.grocery.items if item.kind == "buy"}
    assert bought == {"chicken"} and plan.costs.cash_cents == 1347
    assert plan.costs.from_inventory_cents > 0


def test_inventory_mode_cooks_only_from_what_you_have():
    ing, c = three_dinners(mode=PlanningMode.INVENTORY)
    ing = stock(ing, chicken=1000, rice=1000)
    p = f.problem(c, mains(ing, n=2), ing)
    s = ok(solve(p))
    assert s.estimated_purchase_cents == 0
    plan = build_rounded_plan(p, s, absorb=False)
    assert validate_plan(plan, f.reference(p)).ok
    assert [item.kind for item in plan.grocery.items] == ["from_inventory", "from_inventory"]
    assert plan.costs.cash_cents == 0 and plan.costs.eaten_cents == plan.costs.from_inventory_cents > 0


def test_inventory_mode_explains_exactly_what_is_missing():
    ing, c = three_dinners(mode=PlanningMode.INVENTORY)
    ing = stock(ing, rice=1000)  # no chicken
    result = solve(f.problem(c, mains(ing, n=1), ing))
    assert isinstance(result, SolverInfeasible)
    (short,) = [d for d in result.diagnostics if d.code == "INVENTORY_SHORT"]
    assert short.message.startswith("Your inventory doesn't cover this week.")
    assert "smallest top-up that makes a plan is about $13.47" in short.message
    items = " | ".join(short.items)
    assert "chicken about" in items and "rice" not in items  # rice is in the cupboard


def test_a_top_up_buys_only_the_missing_items():
    ing, c = three_dinners(mode=PlanningMode.INVENTORY, topup_cents=2000)
    ing = stock(ing, rice=1000)
    p = f.problem(c, mains(ing, n=1), ing)
    plan = build_rounded_plan(p, ok(solve(p)), absorb=False)
    assert validate_plan(plan, f.reference(p)).ok
    assert [(i.name, i.kind) for i in plan.grocery.items] == [("chicken", "buy"), ("rice", "from_inventory")]
    assert plan.grocery.total_cents == 1347  # within the $20.00 top-up


def test_a_top_up_too_small_names_what_more_it_needs():
    ing, c = three_dinners(mode=PlanningMode.INVENTORY, topup_cents=1000)
    ing = stock(ing, rice=1000)
    result = solve(f.problem(c, mains(ing, n=1), ing))
    assert isinstance(result, SolverInfeasible)
    (short,) = [d for d in result.diagnostics if d.code == "INVENTORY_SHORT"]
    assert "inventory plus a $10.00 top-up doesn't cover this week" in short.message
    assert "about $13.47" in short.message


# ---------------- waste: opening a perishable pack for a sliver of it ----------------
def sliver_week(cream_grams: int):
    """Two otherwise-equal dinners: 'Creamy' needs some of a 1 kg cream pack ($3.00, perishable, sold only
    in packs); 'Brothy' needs a whole $3.50 carton of shelf-stable broth."""
    ing = {
        1: f.food(1, "filler", 150, offers=[f.offer(11, cents_per_unit="0.1")]),
        2: f.food(2, "cream", 0, perishable=True, offers=[f.offer(21, package=1000, package_cents=300)]),
        3: f.food(3, "broth", 0, unit="ml", offers=[f.offer(31, package=500, package_cents=350)]),
    }
    recipes = [
        f.recipe(1, "Creamy", [D], [f.line(1, 800), f.line(2, cream_grams)], ing, base=2),
        f.recipe(2, "Brothy", [D], [f.line(1, 800), f.line(3, 500, "ml")], ing, base=2),
    ]
    c = f.constraints(days=2, slots={D: 600}, cook_weekdays=(0,), store_ids=(f.PRIMARY,), nudge_pct=0)
    return f.problem(c, recipes, ing)


def test_opening_a_perishable_pack_for_a_sliver_loses_to_a_dearer_recipe():
    p = sliver_week(cream_grams=100)  # uses 10% of the pack: $2.70 of cream would be left to spoil
    s = ok(solve(p))
    assert set(titles(p, s)) == {"Brothy"}  # costs 50¢ more cash, wastes nothing


def test_a_mostly_used_perishable_pack_is_fine():
    p = sliver_week(cream_grams=900)  # uses 90% of the pack
    s = ok(solve(p))
    assert set(titles(p, s)) == {"Creamy"}


# ---------------- no feasible plan ----------------
def test_no_drink_candidates_names_the_drink_slot():
    ing = base_ingredients()
    c = f.constraints(days=2, slots={D: 600, MealSlot.DRINK: 100}, cook_weekdays=(0,))
    result = solve(f.problem(c, mains(ing, n=2), ing))
    assert isinstance(result, SolverInfeasible)
    (diag,) = [d for d in result.diagnostics if d.code == "NO_CANDIDATES_FOR_SLOT"]
    assert diag.slot is MealSlot.DRINK and "No drink recipes" in diag.message


def test_ceiling_below_what_recipes_allow_gives_a_kcal_diagnostic():
    result = solve(one_slot_week([1500], target=500, days=2))
    assert isinstance(result, SolverInfeasible)
    assert any(
        d.code == "KCAL_DAY_ABOVE_CEILING" and "ceiling is 650" in d.message for d in result.diagnostics
    )


def test_all_candidates_needing_missing_equipment_is_an_empty_pool():
    ing = base_ingredients()
    c = f.constraints(days=2, slots={D: 600}, equipment=frozenset({Equipment.STOVETOP}))
    excluded = tuple(
        ExcludedRecipe(
            100 + i, f"Air fryer {i}", frozenset({D}), ("needs equipment you don't have: air_fryer",)
        )
        for i in range(3)
    )
    with pytest.raises(EmptyCandidatePoolError, match="air_fryer"):
        solve(f.problem(c, [], ing, excluded=excluded))


def test_cook_days_without_minutes_give_a_time_diagnostic():
    ing = base_ingredients()
    c = f.constraints(days=2, slots={D: 600}, cook_weekdays=(0,), cook_minutes=0)
    result = solve(f.problem(c, mains(ing, n=2), ing))
    assert isinstance(result, SolverInfeasible)
    assert any(d.code == "COOK_TIME_TOO_SHORT" for d in result.diagnostics)


def test_held_ingredients_are_listed_for_review():
    ing = base_ingredients()
    c = f.constraints(days=2, slots={D: 600, P: 200}, cook_weekdays=(0,))
    held = ExcludedRecipe(
        9,
        "Gelatin pudding",
        frozenset({P}),
        ("held: gelatin, unflavored (possibly beef-derived; allow it in settings if it's fine)",),
        held_ingredients=("gelatin, unflavored",),
    )
    result = solve(f.problem(c, mains(ing, n=2), ing, excluded=(held,)))
    assert isinstance(result, SolverInfeasible)
    by_code = {d.code: d for d in result.diagnostics}
    assert by_code["NO_CANDIDATES_FOR_SLOT"].slot is P
    assert "gelatin, unflavored" in by_code["HELD_INGREDIENTS"].message


# ---------------- general ----------------
@pytest.mark.solve_cache_off
def test_identical_input_gives_an_identical_plan():
    ing = base_ingredients()
    c = f.constraints(slots={L: 560, D: 600})
    p = f.problem(c, mains(ing), ing)
    first, second = ok(solve(p, time_limit_s=30)), ok(solve(p, time_limit_s=30))
    assert first.batches == second.batches and first.meals == second.meals


# Time for building the model and reading the answer on top of the solver's own limit. AC 1.12 was < 15 s
# with the Phase 1 limit of 12 s; the margin is the same with the current limit.
MODEL_BUILD_HEADROOM_S = 3


@pytest.mark.slow
@pytest.mark.perf
def test_thirty_candidates_seven_days_four_slots_solve_quickly():
    """AC 1.12 under the production time limit (opt-in: it measures the wall clock, so it can't be part of the
    deterministic suite). The time limit makes it return its best plan in time on any machine, so the whole
    solve must finish within SOLVER_TIME_LIMIT_SECONDS (30 s since E7) plus the build headroom."""
    rnd = random.Random(7)
    ing = base_ingredients()
    ing[5] = f.food(
        5, "oats", 380, protein=13, carbs=67, offers=[f.offer(51, package=510, package_cents=329)]
    )
    candidates = []
    for i in range(18):
        candidates.append(
            f.recipe(
                100 + i,
                f"Main {i}",
                [L, D],
                [f.line(1, rnd.randint(620, 820)), f.line(2, rnd.randint(260, 380))],
                ing,
                active=rnd.choice([15, 20, 30, 35]),
                mood=rnd.choice([RecipeMood.SIMPLE, RecipeMood.MEDIUM]),
                freezer=rnd.random() < 0.5,
            )
        )
    for i in range(6):
        candidates.append(
            f.recipe(
                200 + i,
                f"Breakfast {i}",
                [B],
                [f.line(3, rnd.randint(350, 600)), f.line(5, rnd.randint(80, 160))],
                ing,
                base=4,
                active=rnd.choice([5, 10, 20]),
                freezer=rnd.random() < 0.5,
            )
        )
    for i in range(6):
        candidates.append(
            f.recipe(300 + i, f"Dessert {i}", [P], [f.line(4, rnd.randint(420, 520))], ing, base=2, active=5)
        )
    p = f.problem(f.constraints(cook_minutes=90), candidates, ing)  # start to finish (V11, step 2b.9)
    limit_s = get_settings().solver_time_limit_seconds
    started = time.monotonic()
    s = ok(solve(p, time_limit_s=limit_s))
    assert time.monotonic() - started < limit_s + MODEL_BUILD_HEADROOM_S
    assert s.status in ("optimal", "feasible") and len(s.meals) == 28
