"""Per-meal, per-day and per-batch cost (step 2b.1, AC 4): each batch's cost is split over its portions by
largest remainder, so meal costs add up to their batch and day costs add up to food eaten, to the cent. Also
the plan's new display fields (cook_note, dish_category, kind, cash_split_display)."""

import re
from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import MealSlot
from app.planning.costing import portion_split
from app.planning.orchestrator import Orchestrator
from app.planning.post_solve import build_rounded_plan
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverSolution
from app.schemas.plans import PlanRequest
from app.services.plans import NOTHING_TO_COOK, cash_split_display, cook_note
from app.services.settings import current_user
from app.testing import factories as f
from app.testing.llm import FakeClock, make_settings

MON = f.MONDAY
DAYS = [MON + timedelta(days=i) for i in range(4)]
B, D = MealSlot.BREAKFAST, MealSlot.DINNER
NORMAL = f.constraints().default_portion_size
WEEK = date(2026, 10, 12)


def ingredients():
    return {
        1: f.food(1, "chicken", 120, perishable=True, offers=[f.offer(11, package=1000, package_cents=1001)]),
        2: f.food(2, "rice", 360, offers=[f.offer(21, package=2000, package_cents=397)]),
        3: f.food(3, "oats", 380, offers=[f.offer(31, package=500, package_cents=263)]),
        4: f.food(4, "salt", 0, staple=True),
    }


def plan_for(batches, meals, days=4):
    ing = ingredients()
    bowl = f.recipe(30, "Chicken bowl", [D], [f.line(1, 700), f.line(2, 310), f.line(4, 5)], ing, base=3)
    oats = f.recipe(31, "Oats", [B], [f.line(3, 170), f.line(1, 10)], ing, base=2)
    c = f.constraints(
        days=days, slots={B: 300, D: 500}, cook_weekdays=(0, 2), store_ids=(f.PRIMARY,), nudge_pct=0
    )
    p = f.problem(c, [bowl, oats], ing)
    solution = SolverSolution("optimal", 0.0, tuple(batches), tuple(meals), {}, frozenset({f.PRIMARY}), 0)
    return build_rounded_plan(p, solution, absorb=False)


def check_sums(plan):
    m = plan.costs
    assert len(m.batch_cents) == len(plan.batches) and len(m.meal_costs) == len(plan.meals)
    for n, batch in enumerate(plan.batches):
        meals = [c.cents for c in m.meal_costs if c.batch_index == n]
        assert len(meals) + batch.portions_to_freeze == batch.portions
        assert max(meals) - min(meals) <= 1  # equal portions differ by at most a cent
    assert sum(m.day_cents.values()) == m.eaten_cents == sum(c.cents for c in m.meal_costs)
    assert sum(m.batch_cents) == m.eaten_cents + m.frozen_portions_cents
    assert m.cash_cents + m.from_inventory_cents == m.eaten_cents + m.frozen_portions_cents + m.leftover_cents


def test_meal_costs_add_up_to_their_batch_and_day_costs_to_food_eaten():
    plan = plan_for(
        [SolvedBatch(30, MON, NORMAL, Decimal(1), 3), SolvedBatch(31, MON, NORMAL, Decimal(1), 4)],
        [
            *(SolvedMeal(day, D, 0) for day in DAYS[:3]),
            *(SolvedMeal(day, B, 1) for day in DAYS[:4]),
        ],
    )
    check_sums(plan)
    m = plan.costs
    # chicken: one $10.01 pack, 720 g used (700 g dinner, 20 g oats), 280 g left (280¢) → 721¢ used,
    # split 700:20 → 701 + 20 (the spare cent to the larger remainder). Rice: 310 g of a $3.97 bag → 62¢
    # (335¢ left). Oats: 340 g of a $2.63 tub → 179¢ (84¢ left).
    assert m.batch_cents == (701 + 62, 20 + 179)
    assert [c.cents for c in m.meal_costs] == [255, 254, 254, 50, 50, 50, 49]  # spare cents to the earliest
    assert m.day_cents == {DAYS[0]: 305, DAYS[1]: 304, DAYS[2]: 304, DAYS[3]: 49}
    assert m.eaten_cents == 763 + 199 and m.frozen_portions_cents == 0


def test_frozen_extra_portions_take_their_share_of_the_batch():
    plan = plan_for(
        [SolvedBatch(30, MON, NORMAL, Decimal(1), 5, 2)],  # 3 dinners + 2 for the freezer
        [SolvedMeal(day, D, 0) for day in DAYS[:3]],
        days=3,
    )
    check_sums(plan)
    m = plan.costs
    assert m.frozen_portions_cents > 0 and m.batch_cents[0] == m.eaten_cents + m.frozen_portions_cents


def test_the_split_gives_spare_cents_to_the_earliest_meals():
    plan = plan_for(
        [SolvedBatch(30, MON, NORMAL, Decimal(1), 3)], [SolvedMeal(day, D, 0) for day in DAYS[:3]], days=3
    )
    costs, frozen = portion_split(plan.batches, plan.meals, [1001])
    assert [c.cents for c in costs] == [334, 334, 333] and frozen == 0


def test_display_helpers():
    assert cash_split_display(5291, 9043) == "$52.91 groceries + $90.43 stock-up"
    assert cash_split_display(5291, 0) == "$52.91 groceries"
    assert cook_note([]) == NOTHING_TO_COOK == "Nothing to cook, eating prepped meals"
    assert cook_note([("Chicken over rice", 5), ("Pudding", 1)]) == (
        "Cook: Chicken over rice (5 portions), Pudding (1 portion)"
    )


def test_a_planned_week_shows_meal_day_and_batch_costs(client, seeded_db):
    user = current_user(seeded_db)
    o = Orchestrator(seeded_db, user.id, llm_client=None, settings=make_settings(), clock=FakeClock())
    out = o.run(PlanRequest(week_start=WEEK, days=3, allow_llm=False))
    assert out.status == "succeeded", out.error
    summary = client.get(f"/api/v1/plans/{out.plan_id}").json()
    costs = summary["costs"]
    assert summary["kind"] is None  # a POST /plans week plan
    assert sum(d["cost_cents"] for d in summary["days"]) == costs["eaten_cents"]
    for day in summary["days"]:
        assert sum(m["cost_cents"] for m in day["meals"]) == day["cost_cents"]
        assert day["cost_display"].startswith("$")
        assert all(m["dish_category"] and m["cost_display"].startswith("$") for m in day["meals"])
    assert sum(b["cost_cents"] for b in summary["batches"]) == (
        costs["eaten_cents"] + costs["frozen_portions_cents"]
    )
    by_batch: dict[int, int] = {}
    for day in summary["days"]:
        for meal in day["meals"]:
            by_batch[meal["cook_batch_id"]] = by_batch.get(meal["cook_batch_id"], 0) + meal["cost_cents"]
    for batch in summary["batches"]:
        if batch["portions_to_freeze"] == 0:
            assert by_batch[batch["id"]] == batch["cost_cents"]
        assert batch["dish_category"] in {"bowl", "roast", "curry", "dessert", "wrap", "oats"}
    tuesday = summary["days"][1]
    assert tuesday["is_cook_day"] is False and tuesday["cook_note"] == "Nothing to cook, eating prepped meals"
    monday = summary["days"][0]
    cooked = [b for b in summary["batches"] if b["cook_on"] == monday["day"]]
    assert monday["cook_note"] == "Cook: " + ", ".join(
        f"{b['title']} ({b['portions']} portion{'s' if b['portions'] != 1 else ''})" for b in cooked
    )
    split = re.fullmatch(r"\$([\d,.]+) groceries( \+ \$([\d,.]+) stock-up)?", costs["cash_split_display"])
    assert split, costs["cash_split_display"]
    glist = client.get(f"/api/v1/plans/{out.plan_id}/grocery-list").json()
    assert glist["cash_split_display"] == costs["cash_split_display"]
    batch = summary["batches"][0]
    detail = client.get(f"/api/v1/cook-batches/{batch['id']}").json()
    assert all(m["cost_cents"] is not None and m["dish_category"] for m in detail["meals"])
