"""The pinned re-solve behind Swap (step 2b.6, FLOW_SPEC §13.3): a diff test. Swapping one meal changes that
meal, the batch that fed it and at most one other batch (a new one, or one more meal from a batch already in
the plan); every other meal and batch stays exactly as it was, and every option is a different recipe."""

from datetime import date, timedelta

from app.domain.enums import MealSlot, PortionSize
from app.planning.pins import KeptBatch, Pins, filled, kept_indices, solve_pinned, swap_options
from app.planning.post_solve import KeptRounding, build_rounded_plan
from app.planning.problem import PlanningProblem, size_multiplier
from app.planning.solver.model import SolverSolution
from app.planning.solver.solve import solve
from app.testing.factories import MONDAY, constraints, food, line, offer, problem, recipe

LUNCH, DINNER = MealSlot.LUNCH, MealSlot.DINNER


def week() -> PlanningProblem:
    """Three days of lunch and dinner, cook days Mon and Wed, six recipes for either meal."""
    foods = {
        i: food(i, name, kcal, protein, offers=[offer(i, cents_per_unit=cents)])
        for i, name, kcal, protein, cents in [
            (1, "chicken", 165, 31, "1.0"),
            (2, "rice", 130, 3, "0.3"),
            (3, "beans", 120, 8, "0.4"),
            (4, "eggs", 155, 13, "0.8"),
            (5, "lentils", 115, 9, "0.35"),
            (6, "tofu", 140, 15, "0.6"),
        ]
    }
    titles = ["Chicken rice", "Bean bowl", "Egg fried rice", "Lentil stew", "Tofu rice", "Chicken beans"]
    pairs = [(1, 2), (3, 2), (4, 2), (5, 2), (6, 2), (1, 3)]
    candidates = [
        recipe(
            n + 1,
            titles[n],
            [LUNCH, DINNER],
            [line(a, 900), line(b, 1000)],
            foods,
            base=4,
            freezer=True,
            active=15,
        )
        for n, (a, b) in enumerate(pairs)
    ]
    c = constraints(
        days=3, slots={LUNCH: 600, DINNER: 700}, cook_weekdays=(0, 2), cook_minutes=120, max_portions=3
    )
    return problem(c, candidates, foods)


def pins_for(p: PlanningProblem, solution: SolverSolution, slot: tuple[date, MealSlot]) -> Pins:
    rounded = build_rounded_plan(p, solution, absorb=False)
    kept: dict[tuple[int, date, str], KeptBatch] = {}
    for b, r in zip(solution.batches, rounded.batches, strict=True):
        key = (b.version_id, b.cook_on, b.portion_size.value)
        base = p.candidate(b.version_id).base_servings
        nudge = r.scale_factor * base / (b.portions * size_multiplier(PortionSize(b.portion_size)))
        kept[key] = KeptBatch(
            key, len(kept), r.title, b.portions, b.portions_to_freeze, nudge, KeptRounding(r.scale_factor)
        )
    keys = [(b.version_id, b.cook_on, b.portion_size.value) for b in solution.batches]
    meals = {(m.eat_on, m.slot): keys[m.batch_index] for m in solution.meals}
    fed = meals.pop(slot)
    offer_ids = frozenset(r.version_id for r in p.candidates) - {fed[0]}
    return Pins(slot, fed, meals, kept, offer_ids, MONDAY)


def batch_keys(solution: SolverSolution) -> dict[tuple[int, date, str], int]:
    return {(b.version_id, b.cook_on, b.portion_size.value): b.portions for b in solution.batches}


def test_a_swap_changes_only_the_meal_and_the_batches_that_feed_it() -> None:
    p = week()
    base = solve(p)
    assert isinstance(base, SolverSolution)
    slot = (MONDAY + timedelta(days=1), DINNER)
    pins = pins_for(p, base, slot)
    found = solve_pinned(p, pins)
    assert found is not None
    swapped, _ = found
    fill = filled(swapped, pins)
    assert pins.fed_by is not None and fill.version_id != pins.fed_by[0]
    before = {(m.eat_on, m.slot): base.batches[m.batch_index] for m in base.meals}
    after = {(m.eat_on, m.slot): swapped.batches[m.batch_index] for m in swapped.meals}
    assert before.keys() == after.keys()
    for key, b in before.items():
        if key == slot:
            continue
        a = after[key]
        assert (a.version_id, a.cook_on, a.portion_size) == (b.version_id, b.cook_on, b.portion_size)
    old, new = batch_keys(base), batch_keys(swapped)
    changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
    assert pins.fed_by in changed and changed <= {pins.fed_by, fill.key}
    for solved in swapped.batches:
        batch_key = (solved.version_id, solved.cook_on, solved.portion_size.value)
        if batch_key in pins.batches:
            assert solved.nudge == pins.batches[batch_key].nudge  # every kept batch keeps its multiplier
    exact, nudge_only = kept_indices(swapped, pins)
    assert {swapped.batches[i].version_id for i in nudge_only} <= {pins.fed_by[0], fill.version_id}
    plan = build_rounded_plan(p, swapped, kept=exact, keep_nudge=nudge_only)
    rounded_before = build_rounded_plan(p, base, absorb=False)
    lines_before = {
        (r.version_id, r.cook_on): r.lines
        for r in rounded_before.batches
        if (r.version_id, r.cook_on, r.portion_size.value) not in changed
    }
    for r in plan.batches:
        if (r.version_id, r.cook_on) in lines_before:
            assert r.lines == lines_before[(r.version_id, r.cook_on)]  # kept batches round exactly as before


def test_the_options_are_different_recipes_and_never_the_ones_swapped_away() -> None:
    p = week()
    base = solve(p)
    assert isinstance(base, SolverSolution)
    slot = (MONDAY + timedelta(days=2), LUNCH)
    pins = pins_for(p, base, slot)
    found, _ = swap_options(p, pins, count=5)
    versions = [filled(s, pins).version_id for s in found]
    assert len(versions) == len(set(versions)) >= 3
    assert pins.fed_by is not None and pins.fed_by[0] not in versions
    away = frozenset(versions[:2])
    again, _ = swap_options(p, Pins(**{**pins.__dict__, "offer": pins.offer - away}), count=5)
    assert not {filled(s, pins).version_id for s in again} & away


def test_a_cooked_batch_never_grows_and_a_new_batch_starts_today_or_later() -> None:
    p = week()
    base = solve(p)
    assert isinstance(base, SolverSolution)
    slot = (MONDAY + timedelta(days=2), DINNER)
    pins = pins_for(p, base, slot)
    cooked = {k: KeptBatch(**{**b.__dict__, "cooked": True}) for k, b in pins.batches.items()}
    late = Pins(**{**pins.__dict__, "batches": cooked, "earliest": MONDAY + timedelta(days=2)})
    found = solve_pinned(p, late)
    if found is not None:
        fill = filled(found[0], late)
        assert fill.new and fill.key[1] >= MONDAY + timedelta(days=2)
    nothing = Pins(**{**late.__dict__, "earliest": MONDAY + timedelta(days=3)})
    assert solve_pinned(p, nothing) is None  # no cook day left from Thursday, and every batch is cooked
