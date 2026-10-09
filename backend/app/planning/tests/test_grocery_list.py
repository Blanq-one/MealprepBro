"""The grocery list from the rounded plan (deliverable 16)."""

from datetime import timedelta
from decimal import Decimal

from app.domain.enums import MealSlot
from app.planning.grocery_list import build_grocery
from app.planning.problem import InventoryLot
from app.planning.rounding import round_batch
from app.planning.solver.model import SolvedBatch
from app.testing import factories as f

MON = f.MONDAY
D = MealSlot.DINNER
NORMAL = f.constraints().default_portion_size
LB = Decimal("453.59237")


def setup(threshold=500, lots_chicken=(), extra_offers=()):
    ing = {
        1: f.food(
            1,
            "chicken",
            120,
            perishable=True,
            lots=lots_chicken,
            offers=[
                f.offer(11, f.PRIMARY, package=3 * LB, package_cents=1347),
                f.offer(12, f.SECONDARY, package=3 * LB, package_cents=1047),
                *extra_offers,
            ],
        ),
        2: f.food(2, "rice", 360, offers=[f.offer(21, f.PRIMARY, package=2268, package_cents=499)]),
        3: f.food(
            3,
            "onion",
            40,
            unit="g",
            piece_grams="110",
            offers=[f.offer(31, f.PRIMARY, cents_per_unit=Decimal(199) / LB)],
        ),
        4: f.ingredient(4, "salt", staple=True, per_100g={"energy_kcal": 0}),
        5: f.food(5, "protein powder", 387),
    }
    c = f.constraints(threshold_cents=threshold)
    a = f.recipe(1, "Chicken rice", [D], [f.line(1, 680), f.line(2, 300), f.line(4, 6)], ing, base=4)
    b = f.recipe(2, "Onion chicken", [D], [f.line(1, 500), f.line(3, 2, "count")], ing, base=4)
    p = f.problem(c, [a, b], ing)
    batches = [
        round_batch(p, SolvedBatch(1, MON, NORMAL, Decimal(1), 4)),
        round_batch(p, SolvedBatch(2, MON + timedelta(days=2), NORMAL, Decimal(1), 4)),
    ]
    return p, batches


def items(plan, name):
    return [i for i in plan.items if i.name == name]


def test_needs_aggregate_across_batches_and_units():
    p, batches = setup()
    plan = build_grocery(p.constraints, batches, p.ingredients)
    (chicken,) = items(plan, "chicken")
    assert chicken.needed == 1180 and set(chicken.recipes) == {"Chicken rice", "Onion chicken"}
    (onion,) = items(plan, "onion")
    assert onion.unit == "g" and onion.needed == 220  # 2 onions × 110 g, priced per pound


def test_staples_are_check_you_have_and_never_costed():
    p, batches = setup()
    plan = build_grocery(p.constraints, batches, p.ingredients)
    (salt,) = items(plan, "salt")
    assert salt.kind == "staple" and salt.note == "check you have" and salt.cost_cents is None


def test_everything_at_the_primary_store_below_the_threshold():
    p, batches = setup(threshold=500)
    plan = build_grocery(p.constraints, batches, p.ingredients)
    assert plan.savings_cents == 300  # one 3 lb chicken pack: $13.47 vs $10.47
    assert not plan.split
    assert all(i.store_id in (None, f.PRIMARY) for i in plan.items)
    plan_low = build_grocery(f.constraints(threshold_cents=300), batches, p.ingredients)
    assert plan_low.split and items(plan_low, "chicken")[0].store_id == f.SECONDARY


def test_totals_are_sums_of_integer_lines_and_group_by_store():
    p, batches = setup()
    plan = build_grocery(p.constraints, batches, p.ingredients)
    lines = [i.cost_cents for i in plan.items if i.cost_cents is not None]
    assert all(isinstance(c, int) for c in lines)
    assert plan.total_cents == sum(lines) == sum(plan.store_cents.values())
    (onion,) = items(plan, "onion")
    assert onion.cost_cents == round(Decimal(220) * Decimal(199) / LB)  # loose: rounded once per line


def test_open_packages_are_used_first():
    lots = [
        InventoryLot(1, 1, Decimal(400), expires_on=MON + timedelta(days=1)),
        InventoryLot(
            2, 1, Decimal(300), opened_on=MON - timedelta(days=1), expires_on=MON + timedelta(days=5)
        ),
    ]
    p, batches = setup(lots_chicken=lots)
    plan = build_grocery(p.constraints, batches, p.ingredients)
    assert plan.inventory_takes[0] == (2, Decimal(300))  # the open package first
    assert plan.inventory_takes[1] == (1, Decimal(400))
    (chicken,) = items(plan, "chicken")
    assert chicken.inventory_used == 700 and chicken.to_buy == 480


def test_inventory_that_covers_the_need_buys_nothing():
    p, batches = setup(lots_chicken=[InventoryLot(1, 1, Decimal(2000))])
    plan = build_grocery(p.constraints, batches, p.ingredients)
    (chicken,) = items(plan, "chicken")
    assert chicken.kind == "from_inventory" and chicken.cost_cents is None and chicken.to_buy == 0


def test_unknown_price_is_flagged_not_guessed():
    p, _ = setup()
    pudding = f.recipe(3, "Pudding", [MealSlot.PROTEIN_DESSERT], [f.line(5, 62)], p.ingredients, base=2)
    p2 = f.problem(p.constraints, [*p.candidates, pudding], dict(p.ingredients))
    batch = round_batch(p2, SolvedBatch(3, MON, NORMAL, Decimal(1), 2))
    plan = build_grocery(p2.constraints, [batch], p2.ingredients)
    (powder,) = items(plan, "protein powder")
    assert powder.kind == "unpriced" and powder.cost_cents is None
    assert not plan.complete and plan.unpriced == ("protein powder",)


def test_expected_remainder_is_shown_on_the_last_buy_line():
    p, batches = setup()
    plan = build_grocery(p.constraints, batches, p.ingredients)
    (chicken,) = items(plan, "chicken")
    assert chicken.remainder == 3 * LB - 1180
    (rice,) = items(plan, "rice")
    assert rice.remainder == 2268 - 300
