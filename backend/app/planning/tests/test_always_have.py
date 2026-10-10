"""Always have (step 2b.1, AC 3): unlimited stock you own. Never bought, never listed (not even under "check
you have"), not deducted when you cook; what the week uses is still costed at its unit price when one is
known, so cash + from inventory = eaten + frozen + leftover holds to the cent. Water is always treated this
way."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    MealPlan,
    PlanBatchIngredient,
    PlanCookBatch,
)
from app.domain.cost import round_cents
from app.domain.enums import MealSlot
from app.planning.inputs import constraints_for
from app.planning.orchestrator import Orchestrator
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverSolution
from app.planning.solver.solve import solve
from app.schemas.plans import PlanRequest
from app.services import cooking
from app.services.plans import grocery_view
from app.services.settings import current_user, load_settings, save_settings
from app.testing import factories as f
from app.testing.llm import FakeClock, make_settings

MON = f.MONDAY
D = MealSlot.DINNER
NORMAL = f.constraints().default_portion_size
OIL_CENTS, OIL_ML = 699, 500
WEEK = date(2026, 10, 12)


def ingredients():
    return {
        1: f.food(
            1,
            "chicken",
            120,
            protein=22,
            perishable=True,
            offers=[f.offer(11, package=1000, package_cents=1000)],
        ),
        2: f.food(2, "rice", 360, carbs=80, offers=[f.offer(21, package=2000, package_cents=400)]),
        3: f.ingredient(
            3,
            "olive oil",
            unit="ml",
            per_100g={"energy_kcal": 884},
            always_have=True,
            offers=[f.offer(31, package=OIL_ML, package_cents=OIL_CENTS)],
        ),
        4: f.ingredient(4, "water", unit="ml", per_100g={"energy_kcal": 0}, always_have=True, staple=True),
        5: f.ingredient(5, "salt", per_100g={"energy_kcal": 0}, always_have=True, staple=True),
        6: f.ingredient(6, "pepper", per_100g={"energy_kcal": 0}, staple=True),  # a plain staple
    }


def bowl(ing):
    lines = [
        f.line(1, 600),
        f.line(2, 300),
        f.line(3, 40, "ml"),
        f.line(4, 540, "ml"),
        f.line(5, 5),
        f.line(6, 1),
    ]
    return f.recipe(30, "Chicken bowl", [D], lines, ing, base=4)


def three_dinners(ing):
    c = f.constraints(days=3, slots={D: 500}, cook_weekdays=(0,), store_ids=(f.PRIMARY,), nudge_pct=0)
    p = f.problem(c, [bowl(ing)], ing)
    meals = tuple(SolvedMeal(MON + timedelta(days=i), D, 0) for i in range(3))
    solution = SolverSolution(
        "optimal", 0.0, (SolvedBatch(30, MON, NORMAL, Decimal(1), 3),), meals, {}, frozenset({f.PRIMARY}), 0
    )
    return p, build_rounded_plan(p, solution, absorb=False)


def test_always_have_items_are_never_bought_or_listed():
    _, plan = three_dinners(ingredients())
    kinds = {item.name: item.kind for item in plan.grocery.items}
    assert kinds["olive oil"] == kinds["water"] == kinds["salt"] == "always_have"
    assert kinds["pepper"] == "staple"  # a plain staple is still "check you have"
    for item in plan.grocery.items:
        if item.kind == "always_have":
            assert item.to_buy == 0 and item.cost_cents is None and item.inventory_used == item.needed
    assert {i.name for i in plan.grocery.items if i.kind == "buy"} == {"chicken", "rice"}
    assert plan.grocery.total_cents == 1000 + 400


def test_what_the_week_uses_is_costed_at_its_unit_price_and_the_money_balances():
    _, plan = three_dinners(ingredients())
    m = plan.costs
    oil_used = 40 * Decimal(3) / 4  # 3 portions of a 4-serving recipe
    assert m.from_inventory_cents == round_cents(oil_used * Decimal(OIL_CENTS) / OIL_ML)
    assert m.complete and m.unpriced == ()  # unpriced water and salt are simply not counted
    assert m.cash_cents + m.from_inventory_cents == m.eaten_cents + m.frozen_portions_cents + m.leftover_cents


def test_the_solver_never_buys_an_always_have_item_and_the_validator_accepts_it():
    ing = ingredients()
    c = f.constraints(days=3, slots={D: 500}, cook_weekdays=(0,), store_ids=(f.PRIMARY,))
    p = f.problem(c, [bowl(ing)], ing)
    s = solve(p)
    assert isinstance(s, SolverSolution), s
    plan = build_rounded_plan(p, s)
    assert not [i for i in plan.grocery.items if i.ingredient_id in (3, 4, 5) and i.kind != "always_have"]
    report = validate_plan(plan, f.reference(p))
    assert report.ok, report.errors


def test_the_constraints_carry_your_always_have_items_and_water(seeded_db):
    user = current_user(seeded_db)
    ids = dict(seeded_db.execute(select(Ingredient.slug, Ingredient.id)).tuples().all())
    request = PlanRequest(week_start=WEEK, days=3)
    assert constraints_for(seeded_db, user.id, request).always_have_ingredient_ids == {ids["water"]}
    settings = load_settings(seeded_db, user.id).model_copy(update={"always_have": ["olive-oil", "salt"]})
    save_settings(seeded_db, user.id, settings)
    c = constraints_for(seeded_db, user.id, request)
    assert c.always_have_ingredient_ids == {ids["water"], ids["olive-oil"], ids["salt"]}


def _plan_with_olive_oil_always_on_hand(session):
    user = current_user(session)
    settings = load_settings(session, user.id).model_copy(update={"always_have": ["olive-oil"]})
    save_settings(session, user.id, settings)
    o = Orchestrator(session, user.id, llm_client=None, settings=make_settings(), clock=FakeClock())
    out = o.run(PlanRequest(week_start=WEEK, days=3, allow_llm=False))
    assert out.status == "succeeded", out.error
    return user, session.get(MealPlan, out.plan_id)


def test_a_planned_week_never_lists_them_and_still_balances(seeded_db):
    user, plan = _plan_with_olive_oil_always_on_hand(seeded_db)
    ids = dict(seeded_db.execute(select(Ingredient.slug, Ingredient.id)).tuples().all())
    used = {
        r.ingredient_id
        for r in seeded_db.scalars(
            select(PlanBatchIngredient)
            .join(PlanCookBatch, PlanCookBatch.id == PlanBatchIngredient.cook_batch_id)
            .where(PlanCookBatch.meal_plan_id == plan.id)
        )
    }
    assert ids["olive-oil"] in used  # the week does cook with it
    view = grocery_view(seeded_db, user.id, plan.id)
    listed = {i.ingredient_id for g in view.groups for i in g.items}
    assert ids["olive-oil"] not in listed and ids["water"] not in listed
    stored = set(
        seeded_db.scalars(
            select(GroceryListItem.ingredient_id)
            .join(GroceryList, GroceryList.id == GroceryListItem.grocery_list_id)
            .where(GroceryList.meal_plan_id == plan.id)
        )
    )
    assert ids["olive-oil"] not in stored and ids["water"] not in stored
    costs = plan.totals["costs"]
    assert costs["cash_cents"] + costs["from_inventory_cents"] == (
        costs["eaten_cents"] + costs["frozen_portions_cents"] + costs["leftover_cents"]
    )
    assert costs["from_inventory_cents"] > 0  # the oil the week uses, at its price


def test_marking_a_batch_cooked_does_not_deduct_always_have_items(seeded_db):
    user, plan = _plan_with_olive_oil_always_on_hand(seeded_db)
    oil = seeded_db.scalars(select(Ingredient.id).where(Ingredient.slug == "olive-oil")).one()
    batch = seeded_db.scalars(
        select(PlanCookBatch)
        .join(PlanBatchIngredient, PlanBatchIngredient.cook_batch_id == PlanCookBatch.id)
        .where(PlanCookBatch.meal_plan_id == plan.id, PlanBatchIngredient.ingredient_id == oil)
    ).first()
    result = cooking.mark_cooked(seeded_db, user.id, batch.id, batch.cook_on)
    assert oil not in {d.ingredient_id for d in result.deductions}
    assert result.deductions  # the rest is still taken (and reported short: nothing was bought)


def test_legacy_lists_never_show_water(seeded_db):
    """Plans saved before this step listed water under "check you have"; the list never shows it now."""
    user = current_user(seeded_db)
    o = Orchestrator(seeded_db, user.id, llm_client=None, settings=make_settings(), clock=FakeClock())
    out = o.run(PlanRequest(week_start=WEEK, days=3, allow_llm=False))
    assert out.status == "succeeded", out.error
    water = seeded_db.scalars(select(Ingredient.id).where(Ingredient.slug == "water")).one()
    glist = seeded_db.scalars(select(GroceryList).where(GroceryList.meal_plan_id == out.plan_id)).one()
    seeded_db.add(
        GroceryListItem(
            grocery_list_id=glist.id,
            position=999,
            ingredient_id=water,
            needed_quantity=Decimal(540),
            inventory_used_quantity=Decimal(0),
            to_buy_quantity=Decimal(0),
            unit="ml",
            reason={"kind": "staple", "note": "check you have", "to_buy_total": "0"},
        )
    )
    plan = seeded_db.get(MealPlan, out.plan_id)
    plan.constraints = {k: v for k, v in plan.constraints.items() if k != "always_have_ingredient_ids"}
    seeded_db.flush()
    view = grocery_view(seeded_db, user.id, out.plan_id)
    assert water not in {i.ingredient_id for g in view.groups for i in g.items}
