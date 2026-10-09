"""Settings + week + per-day choices → PlanConstraints (deliverable 3)."""

from datetime import date

import pytest

from app.domain.enums import CalorieMode, MealSlot, PlanningMode, RecipeMood
from app.domain.exclusions import ExclusionStatus
from app.domain.frequency_caps import ResolvedCap
from app.planning.constraint_builder import ConstraintError, DietInputs, build_constraints
from app.schemas.plans import DayOverride, PlanRequest
from app.seed.files import load_seed_files

WEEK = date(2026, 10, 12)  # a Monday
STORES = {"Stop & Shop": 1, "Price Rite": 2}
DIET = DietInputs(
    statuses={
        1: ExclusionStatus.ALLOWED,
        2: ExclusionStatus.EXCLUDED,
        3: ExclusionStatus.HELD,
        4: ExclusionStatus.EXCLUDED,
    },
    caps=(
        ResolvedCap("Pork as a meal component", frozenset({5, 6}), 1, True),
        ResolvedCap("Zero", frozenset({4}), 0, True),
    ),
    disliked_ids=frozenset({7, 2}),
)


def build(**request):
    return build_constraints(
        load_seed_files().settings, PlanRequest(week_start=WEEK, **request), DIET, STORES
    )


def test_default_week_follows_your_schedule():
    c = build()
    assert [d.is_cook_day for d in c.days] == [True, False, True, True, False, True, True]
    for d in c.days:
        if not d.is_cook_day:
            assert d.cook_minutes_available == 0
        else:
            assert d.cook_minutes_available == 45 and d.mood is RecipeMood.MEDIUM
    assert c.calorie_mode is CalorieMode.WEEKLY and c.weekly_kcal_target == 12600
    assert [d.kcal_target for d in c.days] == [1800] * 7
    assert c.store_ids == (1, 2) and c.store_split_min_savings_cents == 500
    assert c.leftover_fridge_days == 3


def test_exclusions_held_items_and_caps_are_resolved():
    c = build()
    assert c.excluded_ingredient_ids == {2, 3, 4} and c.held_ingredient_ids == {3}
    assert [(cap.label, cap.max_meals_per_week) for cap in c.frequency_caps] == [
        ("Pork as a meal component", 1)
    ]
    assert c.disliked_ingredient_ids == {7}  # an excluded item isn't also "disliked"


def test_day_overrides_and_slot_changes_apply_to_this_plan_only():
    c = build(
        day_overrides=[
            DayOverride(day=WEEK, cook_minutes=90, mood=RecipeMood.FANCY),
            DayOverride(day=date(2026, 10, 13), is_cook_day=True, cook_minutes=20),
        ],
        slot_kcal={MealSlot.DINNER: 550, MealSlot.DRINK: 100},
    )
    assert (c.days[0].cook_minutes_available, c.days[0].mood) == (90, RecipeMood.FANCY)
    assert c.days[1].is_cook_day and c.days[1].cook_minutes_available == 20
    assert MealSlot.DRINK in c.days[0].slots and c.slot_target(MealSlot.DINNER).kcal == 550


def test_slot_allocations_over_the_daily_target_are_rejected():
    with pytest.raises(ConstraintError, match="more than your daily target"):
        build(slot_kcal={MealSlot.DRINK: 200})


def test_shop_mode_budget_is_a_per_request_hard_limit():
    c = build(budget_cents=6000, calorie_mode=CalorieMode.STRICT_DAILY)
    assert (c.planning_mode, c.purchase_limit_cents, c.has_purchase_limit) == (PlanningMode.SHOP, 6000, True)
    assert c.calorie_mode is CalorieMode.STRICT_DAILY
    no_budget = build()
    assert (no_budget.planning_mode, no_budget.purchase_limit_cents) == (PlanningMode.SHOP, None)


def test_inventory_mode_buys_nothing_unless_a_top_up_is_allowed():
    assert build(mode=PlanningMode.INVENTORY).purchase_limit_cents == 0
    assert build(mode=PlanningMode.INVENTORY, topup_cents=1200).purchase_limit_cents == 1200


@pytest.mark.parametrize(
    ("request_kwargs", "message"),
    [
        ({"mode": PlanningMode.INVENTORY, "budget_cents": 500}, "inventory mode takes a top-up"),
        ({"mode": PlanningMode.SHOP, "topup_cents": 500}, "a top-up is for inventory mode"),
    ],
)
def test_a_limit_for_the_other_mode_is_rejected(request_kwargs, message):
    with pytest.raises(ValueError, match=message):
        PlanRequest(week_start=WEEK, **request_kwargs)


def test_protein_target_comes_from_settings_or_the_request():
    assert build().daily_protein_target_g == 100  # your default
    assert build(protein_target_g=120).daily_protein_target_g == 120
    assert build(protein_target_g=0).daily_protein_target_g == 0


def test_the_budget_is_no_longer_a_setting():
    assert "weekly_budget_cents" not in load_seed_files().settings.model_dump()


def test_constraint_hash_is_stable():
    assert build().content_hash() == build().content_hash()
    assert build().content_hash() != build(budget_cents=1).content_hash()
    assert build().content_hash() != build(protein_target_g=101).content_hash()
