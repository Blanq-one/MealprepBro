"""The shortlist regression and the time/mood "no plan fits" message (2b.3b approval, P3 and P4).

P3: with the M13 library, a week of seven 45-minute cook days (two of them simple) with a protein dessert
and a stocked pantry returned "No plan fits": the shortlist ignored hands-on time, so Monday (which cooks
every one of its meals itself) got only slow recipes. Each meal's shortlist now keeps its quickest recipe, and
the planner tries every eligible recipe before it says no plan fits.
P4: a time or mood blocker is said once, in plain words, with the fix the app can offer.
"""

import time
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.models import GenerationRun, Ingredient
from app.domain.enums import PlanningMode, StorageLocation
from app.llm.pacing import SystemClock
from app.planning.orchestrator import Orchestrator
from app.schemas.plans import DayOverride, PlanRequest, RunSolveRecord
from app.services.inventory import LotInput, add_lot
from app.services.settings import current_user, patch_settings
from app.testing.llm import FakeClock, make_settings

WEEK = date(2026, 10, 12)  # a Monday


def plan(session, **request):
    user = current_user(session)
    o = Orchestrator(session, user.id, llm_client=None, settings=make_settings(), clock=FakeClock())
    return o.run(PlanRequest(week_start=WEEK, allow_llm=False, **request))


def test_default_settings_and_the_seed_library_always_plan_a_shop_week_with_no_budget(seeded_db):
    out = plan(seeded_db, mode=PlanningMode.SHOP)
    assert out.status == "succeeded", out.error


# The settings and pantry of the report (dev database, 2026-10-11), with its 45 hands-on minutes a cook day
# converted to 90 start to finish (V11, migration 0008).
EVERY_DAY = [
    {
        "weekday": d,
        "is_cook_day": True,
        "cook_minutes": 90,
        "mood": "simple" if d in ("tue", "fri") else "medium",
    }
    for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
]
PANTRY = [
    ("egg-large", 12, "count", "fridge"),
    ("bell-pepper", 2, "count", "fridge"),
    ("milk-2", 3785, "ml", "fridge"),
    ("tomato", 7, "count", "fridge"),
    ("flour-tortilla-small", 20, "count", "pantry"),
    ("rice-long-grain-white", 1810, "g", "pantry"),
    ("cauliflower", 812, "g", "freezer"),
    ("chicken-thigh-boneless-skinless", 454, "g", "fridge"),
    ("spinach-frozen", 227, "g", "freezer"),
    ("ghee", 473, "ml", "pantry"),
    ("onion-yellow", 907, "g", "pantry"),
    ("chia-seeds", 340, "g", "pantry"),
    ("protein-powder-double-chocolate", 2268, "g", "pantry"),
    ("cauliflower-frozen", 283, "g", "freezer"),
    ("kidney-beans-dried", 454, "g", "pantry"),
    ("peas-frozen", 340, "g", "freezer"),
    ("peanut-butter", 454, "g", "pantry"),
    ("bread-whole-wheat", 20, "count", "pantry"),
    ("potato-russet", 2268, "g", "pantry"),
    ("broccoli-frozen", 283, "g", "freezer"),
]


def use_dev_settings(session) -> None:
    """Your dev database's settings and pantry: seven 90-minute cook days, 4 meals a day."""
    user = current_user(session)
    patch_settings(
        session,
        user.id,
        {
            "cook_schedule": EVERY_DAY,
            "slot_allocations": [
                {"slot": "breakfast", "kcal": 325},
                {"slot": "lunch", "kcal": 575},
                {"slot": "dinner", "kcal": 700},
                {"slot": "protein_dessert", "kcal": 200},
            ],
            "equipment": [
                "stovetop",
                "oven",
                "air_fryer",
                "microwave",
                "pressure_cooker",
                "rice_cooker",
                "slow_cooker",
                "blender",
                "food_processor",
            ],
        },
    )
    for slug, quantity, unit, location in PANTRY:
        ingredient = session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()
        add_lot(session, user.id, LotInput(ingredient, Decimal(quantity), unit, StorageLocation(location)))


@pytest.mark.slow  # a full week with cut re-solves, about 3-4 minutes: --run-slow (step 2b.9)
def test_seven_cook_days_a_protein_dessert_and_a_stocked_pantry_plan_again(seeded_db):
    use_dev_settings(seeded_db)
    out = plan(seeded_db, mode=PlanningMode.SHOP)
    assert out.status == "succeeded", out.error
    assert any(b.cook_on == WEEK for b in out.plan.batches)
    assert out.plan.totals.elapsed_minutes[WEEK] <= 90  # Monday's schedule, start to finish


WELL_INSIDE_S = 90  # half of the 180 s budget


@pytest.mark.perf  # the real clock and the production limits: RUN_PERF_TESTS=1
def test_a_big_week_on_your_settings_plans_well_inside_the_time_budget(seeded_db):
    """Y4: seven cook days and 4 meals a day (your dev settings), planned with the production limits and the
    real clock, finish well inside the 180 s budget, and the time guard never has to cut a solve short. Before
    the day repairs this took 171-245 s."""
    use_dev_settings(seeded_db)
    user = current_user(seeded_db)
    settings = get_settings()
    clock = SystemClock()
    started = time.monotonic()
    out = Orchestrator(seeded_db, user.id, llm_client=None, settings=settings, clock=clock).run(
        PlanRequest(week_start=WEEK, allow_llm=False, mode=PlanningMode.SHOP)
    )
    took = time.monotonic() - started
    record = RunSolveRecord.model_validate(seeded_db.get(GenerationRun, out.run_id).progress["solve"])
    budget_s = settings.plan_time_budget_seconds
    print(
        f"\nbig week: {took:.1f} s of the {budget_s} s budget; {record.solves} solves, "
        f"{record.week_solves} weekly ({record.week_seconds:.1f} s), {record.repairs} day repairs "
        f"({record.repair_seconds:.1f} s), {record.rounding_resolves} rounding re-solves, "
        f"{record.stopped_on_time} stopped on their own limit, proven best: {record.proven_best}"
    )
    assert out.status == "succeeded", out.error
    assert out.report is not None and out.report.ok
    assert all(minutes <= 90 for minutes in out.plan.totals.elapsed_minutes.values())
    # the time guard never cut in: no solve shortened or skipped, never out of time
    assert record.shortened == 0 and record.skipped == 0 and not record.ran_out_of_time
    assert took <= WELL_INSIDE_S


def test_a_time_or_mood_blocker_is_said_once_in_plain_words_with_its_fix(seeded_db):
    three_days = [WEEK + timedelta(days=i) for i in range(3)]
    tight = [DayOverride(day=d, cook_minutes=20, mood="simple") for d in three_days]
    out = plan(seeded_db, days=3, day_overrides=tight)
    assert out.status == "infeasible"
    detail = out.error["detail"]
    assert ".;" not in detail and ";." not in detail and "×" not in detail and "(short by" not in detail
    time = [d for d in out.diagnostics if d.code == "COOK_TIME_SHORT"]
    assert time, out.diagnostics
    first = time[0]
    assert first.message.startswith(f"{first.day:%A} needs about ")
    assert first.message.endswith(" start to finish; you set 20 min.")
    assert first.suggested_minutes is not None and first.suggested_minutes % 5 == 0  # rounded up to 5
    left_out = next(d for d in out.diagnostics if d.code == "RECIPES_LEFT_OUT")
    assert left_out.message.startswith(f"{left_out.amount} recipes") or " are medium" in left_out.message
    assert "and your cook days are set to simple" in left_out.message
    assert left_out.mood == "fancy"  # "Allow fancy recipes"
    messages = [d.message for d in out.diagnostics]
    assert len(messages) == len(set(messages))
    as_json = {d["code"]: d for d in out.error["diagnostics"]}
    assert as_json["COOK_TIME_SHORT"]["suggested_minutes"] == first.suggested_minutes
    assert as_json["RECIPES_LEFT_OUT"]["mood"] == "fancy"
