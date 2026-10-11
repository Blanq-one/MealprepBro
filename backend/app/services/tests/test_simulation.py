"""The steady-state check: week 2 plans from what week 1 leaves behind (dry run)."""

from datetime import date

import pytest

from app.schemas.plans import PlanRequest
from app.services.inventory import list_lots
from app.services.plans import run_plan_now
from app.services.settings import current_user
from app.services.simulation import carry_over, format_table, simulate

WEEK = date(2026, 10, 12)


def test_leftovers_carry_over_frozen_protein_and_stock_up_but_not_at_risk_food(seeded_db):
    user = current_user(seeded_db)
    out = run_plan_now(seeded_db, user.id, PlanRequest(week_start=WEEK, allow_llm=False), None)
    assert out.status == "succeeded" and out.plan is not None
    plan = out.plan
    carried = carry_over(seeded_db, user.id, plan)
    lots = {lot.ingredient_id: lot for lot in list_lots(seeded_db, user.id)}
    kept = [item for item in plan.leftovers if item.fate != "at_risk"]
    assert len(carried) == len(kept) == len(lots)
    for item in plan.leftovers:
        if item.fate == "at_risk":
            assert item.ingredient_id not in lots  # expected waste: not carried
        elif item.fate == "freeze":
            assert lots[item.ingredient_id].location == "freezer"  # raw protein, frozen on shopping day
        else:
            assert lots[item.ingredient_id].location in ("pantry", "fridge")
    assert any(item.name == "protein powder, double chocolate" for item in carried)  # the rest of the tub


@pytest.mark.slow  # one of the heaviest solver tests: --run-slow (2b.3b approval, P6)
def test_week_two_plans_from_week_ones_leftovers(seeded_db):
    user = current_user(seeded_db)
    sim = simulate(seeded_db, user.id, WEEK, 2, last_week_budget_cents=5000)
    first, second, second_budget = sim.runs
    assert [r.label for r in sim.runs] == ["week 1", "week 2", "week 2, budget $50.00"]
    assert first.plan is not None and second.plan is not None and second_budget.plan is not None
    assert second.plan.costs.from_inventory_cents > 0  # frozen chicken, the powder tub, rice
    assert second.plan.costs.stock_up_cash_cents < first.plan.costs.stock_up_cash_cents
    assert second_budget.plan.costs.regular_cash_cents <= 5000
    assert len(sim.carried) == 1 and sim.carried[0]
    table = format_table(sim)
    assert "Oct 12 (week 1)" in table and "Oct 19 (week 2, budget $50.00)" in table
