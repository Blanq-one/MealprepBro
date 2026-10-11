"""The joint nudge snap: one nudge per batch, chosen on the ROUNDED values, so the plan meets your limits."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.domain.enums import CalorieMode, MealSlot
from app.planning import snap
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import Tightening
from app.planning.snap import snap_batches, stepiest_batch
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverSolution, batch_plan
from app.testing import factories as f

THU = date(2026, 10, 15)
B, L = MealSlot.BREAKFAST, MealSlot.LUNCH
NORMAL = f.constraints().default_portion_size


def egg_day(nudge_pct: float = 10.0, protein_g: int = 0):
    """Strict daily mode, 1,800 kcal ceiling: an egg breakfast planned at 54 kcal and a 1,741 kcal lunch."""
    ing = {
        1: f.ingredient(
            1, "egg", unit="count", piece_grams="50", per_100g={"energy_kcal": 143, "protein_g": "12.6"}
        ),
        2: f.food(2, "lunch food", 100, protein=10),
    }
    c = f.constraints(
        week_start=THU,
        days=1,
        slots={B: 500, L: 1300},
        cook_weekdays=(3,),
        calorie_mode=CalorieMode.STRICT_DAILY,
        nudge_pct=nudge_pct,
        cook_minutes=60,
        protein_g=protein_g,
    )
    breakfast = f.recipe(10, "Egg scramble", [B], [f.line(1, 3, "count")], ing, base=4)
    lunch = f.recipe(20, "Big lunch", [L], [f.line(2, "1741.375")], ing, base=1)
    p = f.problem(c, [breakfast, lunch], ing)
    raw = SolverSolution(
        "optimal",
        0.0,
        (SolvedBatch(10, THU, NORMAL, Decimal(1), 1), SolvedBatch(20, THU, NORMAL, Decimal(1), 1)),
        (SolvedMeal(THU, B, 0), SolvedMeal(THU, L, 1)),
        {},
        frozenset({f.PRIMARY}),
        0,
    )
    return p, raw


@pytest.fixture
def lumpy_rounding(monkeypatch):
    """Rounding in steps: each batch rounds 6 kcal over plan at a nudge of 1 or more, 10 under below it.
    Closest-to-plan for each batch alone (60 + 1,747) is 7 kcal over the 1,800 ceiling."""

    def option(problem, batch, nudge):
        planned = {10: 54, 20: 1741}[batch.version_id]
        kcal = planned + 6 if nudge >= 1 else planned - 10
        return snap._Option(nudge, kcal, kcal)  # protein in tenths: same numbers, for the protein test

    monkeypatch.setattr(snap, "_option", option)
    monkeypatch.setattr(
        snap, "_planned_kcal", lambda problem, batch: {10: 54.0, 20: 1741.0}[batch.version_id]
    )


def test_snapping_each_batch_alone_would_go_over_but_the_joint_snap_fits(lumpy_rounding):
    p, raw = egg_day()
    snapped = snap_batches(p, raw)
    assert snapped is not None
    assert sorted(b.nudge < 1 for b in snapped) == [False, True]  # exactly one batch gives 10 kcal


def test_the_joint_snap_meets_the_protein_floor_too(lumpy_rounding):
    p, raw = egg_day(protein_g=180)  # 180 g = 1,800 tenths: the 1,791-tenth combinations don't make it
    assert snap_batches(p, raw) is None  # the per-batch snap and the validator's re-solve take over


def test_nothing_to_choose_without_a_nudge_range():
    p, raw = egg_day(nudge_pct=0)
    assert snap_batches(p, raw) is None


def test_frozen_extra_batches_keep_their_nudge(lumpy_rounding):
    p, raw = egg_day()
    frozen = replace(raw.batches[0], portions=2, portions_to_freeze=1)
    snapped = snap_batches(p, replace(raw, batches=(frozen, raw.batches[1])))
    assert snapped is not None and snapped[0].nudge == 1 and snapped[1].nudge < 1


def test_a_rounded_plan_from_the_real_rounding_passes_the_validator():
    p, raw = egg_day()
    plan = build_rounded_plan(p, raw, absorb=False)
    assert validate_plan(plan, f.reference(p)).ok
    assert 1710 <= plan.totals.day_kcal[THU] <= 1800


# ---------------- no combination fits: the re-solve leaves out the stepiest batch (2b.5) ----------------
def test_the_stepiest_batch_is_the_whole_egg_one():
    """One portion of the egg breakfast is one whole egg at any nudge (it can't move), the lunch moves in
    10 kcal steps: when no nudge combination rounds into the limits, the egg batch is the one to leave out."""
    p, raw = egg_day()
    assert stepiest_batch(p, raw) == 0


def test_a_left_out_batch_is_never_offered_again_on_that_day():
    p, _ = egg_day()
    assert any(b.recipe.version_id == 10 for b in batch_plan(p))
    blocked = p.with_tightening(Tightening(forbidden=frozenset({(10, THU)})))
    assert not any(b.recipe.version_id == 10 for b in batch_plan(blocked))
    assert any(b.recipe.version_id == 20 for b in batch_plan(blocked))
