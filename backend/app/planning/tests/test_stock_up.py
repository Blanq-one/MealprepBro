"""Stock-up items (protein powder, rice): outside a shop-mode budget, bought as the cheapest pack per gram,
listed apart; items priced only at "Other" don't count as a store split; a tight budget that leaves no time
falls back to the cheapest plan."""

from decimal import Decimal

import pulp
import pytest

from app.domain.cost import round_cents
from app.domain.enums import MealSlot, PlanningMode
from app.planning.orchestrator import PlanOutcome
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.solver import model
from app.planning.solver import solve as solve_module
from app.planning.solver.model import SolverInfeasible, SolverSolution
from app.planning.solver.solve import solve
from app.planning.text_report import format_plan
from app.testing import factories as f

D, P = MealSlot.DINNER, MealSlot.PROTEIN_DESSERT
OTHER = 3
STORES = {f.PRIMARY: "Stop & Shop", f.SECONDARY: "Price Rite", OTHER: "Other"}


@pytest.fixture(autouse=True)
def no_margins(monkeypatch):
    monkeypatch.setattr(model, "ROUNDING_MARGIN_DAY_KCAL", 0)
    monkeypatch.setattr(model, "ROUNDING_MARGIN_WEEK_KCAL", 0)


def powder_week(*, mode=PlanningMode.SHOP, budget_cents=None, topup_cents=0, dessert_alternative=False):
    """Three dinners (chicken and rice) and three protein desserts (one scoop of powder each), cooked
    Monday. Chicken: a $10.00 kg pack. Rice: a $4.00 bag (stock-up). Powder: only at "Other", a $62.50
    5 lb tub or a $26.31 small tub (stock-up)."""
    ing = {
        1: f.food(
            1,
            "chicken",
            120,
            protein=22,
            perishable=True,
            offers=[f.offer(11, package=1000, package_cents=1000)],
        ),
        2: f.food(2, "rice", 360, stock_up=True, offers=[f.offer(21, package=2000, package_cents=400)]),
        3: f.food(
            3,
            "protein powder",
            387,
            protein=77,
            stock_up=True,
            offers=[
                f.offer(31, OTHER, package=2268, package_cents=6250),
                f.offer(32, OTHER, package=682, package_cents=2631),
            ],
        ),
        4: f.food(4, "yogurt", 60, protein=10, offers=[f.offer(41, cents_per_unit="0.6")]),
    }
    dinner = f.recipe(10, "Chicken rice", [D], [f.line(1, 700), f.line(2, 330)], ing, base=4)
    pudding = f.recipe(20, "Protein pudding", [P], [f.line(3, 62)], ing, base=2)  # a scoop each
    recipes = [dinner, pudding]
    if dessert_alternative:  # no powder: a dearer yogurt bowl from the primary store
        recipes.append(f.recipe(21, "Yogurt bowl", [P], [f.line(4, 400)], ing, base=2))
    c = f.constraints(
        days=3,
        slots={D: 510, P: 120},
        cook_weekdays=(0,),
        store_ids=(f.PRIMARY, OTHER),
        mode=mode,
        budget_cents=budget_cents,
        topup_cents=topup_cents,
    )
    return f.problem(c, recipes, ing)


def ok(result) -> SolverSolution:
    assert isinstance(result, SolverSolution), getattr(result, "diagnostics", result)
    return result


def test_a_week_needing_a_new_powder_tub_still_fits_a_50_dollar_regular_budget():
    p = powder_week(budget_cents=5000)
    plan = build_rounded_plan(p, ok(solve(p)))
    report = validate_plan(plan, f.reference(p))
    assert report.ok, report.errors
    m = plan.costs
    assert m.regular_cash_cents == 1000  # the chicken, the only regular purchase: within $50.00
    assert m.stock_up_cash_cents == 6250 + 400 and m.cash_cents == 7650  # the tub and the rice are outside it
    powder = [i for i in plan.grocery.items if i.name == "protein powder" and i.kind == "buy"]
    assert [(i.packages, i.cost_cents, i.store_id) for i in powder] == [(1, 6250, OTHER)]  # cheaper per gram
    # food eaten counts the powder by the gram: 3 portions of 31 g at $62.50 / 2,268 g
    # food eaten counts what the week uses at what you pay per gram: powder at $62.50 / 2,268 g (about
    # 86¢ a 31 g scoop), rice at $4.00 / 2 kg, chicken at $10.00 / kg
    needed = {i.name: i.needed for i in plan.grocery.items if i.kind == "buy"}
    rates = {"chicken": Decimal(1), "rice": Decimal("0.2"), "protein powder": Decimal(6250) / 2268}
    expected = sum(round_cents(needed[name] * rate) for name, rate in rates.items())
    assert abs(m.eaten_cents - expected) <= 2  # each line rounded once
    text = format_plan(plan, PlanOutcome("succeeded", 1, plan=plan, report=report), STORES, set())
    assert "Cash this trip        $76.50  whole packages: $10.00 regular + $66.50 stock-up" in text
    assert "Also buy this week (stock-up, lasts beyond this week): $66.50" in text
    assert "protein powder" in text and "at Other" in text
    assert "budget: $50.00 on regular groceries this trip" in text


def test_the_budget_still_binds_the_regular_groceries():
    result = solve(powder_week(budget_cents=900))  # less than the chicken pack
    assert isinstance(result, SolverInfeasible)
    (short,) = [d for d in result.diagnostics if d.code == "BUDGET_SHORT"]
    assert "costs about $10.00 in regular groceries, $1.00 over your budget of $9.00" in short.message
    items = " | ".join(short.items)
    assert "protein powder" not in items and "rice" not in items  # not under the budget


def test_an_inventory_top_up_covers_stock_up_items_too():
    result = solve(powder_week(mode=PlanningMode.INVENTORY, topup_cents=5000))
    assert isinstance(result, SolverInfeasible)
    (short,) = [d for d in result.diagnostics if d.code == "INVENTORY_SHORT"]
    assert any("protein powder" in i for i in short.items) and "about $76.50" in short.message
    assert short.suggested_cents == 7700  # $76.50, rounded up to whole dollars


def test_buying_powder_at_other_is_not_a_store_trip():
    """With a $5 split charge on "Other", the dearer yogurt bowl would win; powder is only sold there, so
    there is no store choice to pay for."""
    p = powder_week(dessert_alternative=True)
    s = ok(solve(p))
    desserts = {p.candidate(s.batches[m.batch_index].version_id).title for m in s.meals if m.slot is P}
    assert desserts == {"Protein pudding"}
    plan = build_rounded_plan(p, s)
    assert not plan.grocery.split and plan.grocery.forced_elsewhere == ("protein powder",)


def test_a_tight_budget_with_no_time_left_falls_back_to_the_cheapest_plan(monkeypatch):
    real = solve_module.run_solver
    calls = []

    def first_times_out(m, *args):
        calls.append(m)
        return pulp.LpSolutionNoSolutionFound if len(calls) == 1 else real(m, *args)

    monkeypatch.setattr(solve_module, "run_solver", first_times_out)
    p = powder_week(budget_cents=5000)
    s = ok(solve(p))
    assert s.status == "cheapest" and len(calls) == 2
    plan = build_rounded_plan(p, s)
    assert validate_plan(plan, f.reference(p)).ok
    assert any(n.startswith("Your budget is tight") for n in plan.notes)
