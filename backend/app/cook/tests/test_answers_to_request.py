"""Meal-prep answers → the plan request (2b.5 deliverables 1 and 7; FLOW_SPEC C1, C1b, C2, C3, C3b, §13.3).
Pure: your default settings and a fixed today."""

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from app.cook.prep import PrepAnswersError, protein_target, resolve_prep, summary
from app.domain.enums import GroceryMode, MealSlot, NutritionPriority, PlanningMode, RecipeMood
from app.schemas.cook import CookAnswers
from app.schemas.settings import UserSettings
from app.seed.files import DATA_DIR

TODAY = date(2026, 10, 14)  # a Wednesday
SETTINGS = UserSettings.model_validate(json.loads((DATA_DIR / "settings_default.json").read_text("utf-8")))
B, L, D, P = MealSlot.BREAKFAST, MealSlot.LUNCH, MealSlot.DINNER, MealSlot.PROTEIN_DESSERT


def answers(prep: dict[str, Any] | None = None, **rest: Any) -> CookAnswers:
    return CookAnswers.model_validate(
        {"mode": "prep", "prep": prep or {"shape": "portions", "slot": "lunch", "portions": 5}, **rest}
    )


def test_five_lunches_from_today_are_lunch_on_five_days_with_that_share_of_your_protein():
    plan = resolve_prep(answers(), SETTINGS, TODAY)
    r = plan.request
    assert (r.week_start, r.days, plan.slots) == (TODAY, 5, (L,))
    assert r.slot_kcal == {B: 0, L: 550, D: 0, P: 0}
    assert r.protein_target_g == 31  # 100 g × 550 / 1,800 kcal
    assert r.day_overrides == []  # mix it up: your cook days
    assert r.mode is PlanningMode.SHOP and r.budget_cents is None
    assert plan.header == "5 lunches · Wed 14 – Sun 18"


def test_by_days_with_several_meals_and_my_usual_week():
    two = resolve_prep(
        answers({"shape": "days", "day_count": 5, "slots": ["dinner", "lunch"], "start": "tomorrow"}),
        SETTINGS,
        TODAY,
    )
    assert (two.start, two.days, two.slots) == (TODAY + timedelta(days=1), 5, (L, D))
    assert two.request.protein_target_g == 67  # 100 × 1,200 / 1,800
    usual = resolve_prep(
        answers(
            {"shape": "days", "day_count": 7, "slots": ["breakfast", "lunch", "dinner", "protein_dessert"]}
        ),
        SETTINGS,
        TODAY,
    )
    assert usual.request.protein_target_g == 100  # every meal: your whole target
    assert usual.request.slot_kcal == {B: 400, L: 550, D: 650, P: 200}


def test_one_big_cook_day_cooks_everything_that_day_with_its_own_minutes():
    plan = resolve_prep(
        answers(
            {
                "shape": "days",
                "day_count": 7,
                "slots": ["lunch", "dinner"],
                "cook_style": "big_day",
                "cook_day": "today",
                "cook_minutes": 300,
            }
        ),
        SETTINGS,
        TODAY,
    )
    cook = [(o.day, o.is_cook_day, o.cook_minutes) for o in plan.request.day_overrides]
    assert cook[0] == (TODAY, True, 300)  # well above the usual 45
    assert all(not is_cook and minutes == 0 for _, is_cook, minutes in cook[1:])
    default = resolve_prep(answers({**_big("today"), "cook_minutes": None}), SETTINGS, TODAY)
    assert default.request.day_overrides[0].cook_minutes == 45  # Wednesday's own minutes


def _big(day: str) -> dict[str, Any]:
    return {"shape": "portions", "slot": "lunch", "portions": 5, "cook_style": "big_day", "cook_day": day}


def test_a_cook_day_outside_the_plan_is_refused():
    with pytest.raises(PrepAnswersError, match="Cook on a day of the plan"):
        resolve_prep(answers({**_big("today"), "start": "tomorrow"}), SETTINGS, TODAY)


def test_a_few_sessions_cook_only_on_the_days_you_pick():
    sessions = [{"day": str(TODAY), "minutes": 60}, {"day": str(TODAY + timedelta(days=3)), "minutes": 90}]
    plan = resolve_prep(
        answers(
            {
                "shape": "days",
                "day_count": 7,
                "slots": ["dinner"],
                "cook_style": "sessions",
                "sessions": sessions,
            }
        ),
        SETTINGS,
        TODAY,
    )
    cook = {o.day: o.cook_minutes for o in plan.request.day_overrides if o.is_cook_day}
    assert cook == {TODAY: 60, TODAY + timedelta(days=3): 90}


def test_same_dish_many_portions_is_one_recipe_per_meal_without_the_weekly_cap():
    plan = resolve_prep(
        answers(
            {
                "shape": "portions",
                "slot": "dinner",
                "portions": 8,
                "cook_style": "same_dish",
                "cook_day": "today",
                "extra_to_freeze": 2,
            }
        ),
        SETTINGS,
        TODAY,
    )
    (req,) = plan.request.portion_requests
    assert req.slot is D and req.same_recipe and len(req.days) == 8 and req.extra_portions_to_freeze == 2
    assert plan.request.max_portions_per_recipe == 14  # F22: the 5-portion cap doesn't apply


def test_goals_map_to_the_planner():
    plan = resolve_prep(
        answers(
            goals=["iron_rich", "high_protein", "cheap", "low_calorie", "quick"],
            time_limit_minutes=25,
            mood="simple",
        ),
        SETTINGS,
        TODAY,
    )
    r = plan.request
    assert (r.nutrition_priority, r.secondary_priority) == (NutritionPriority.IRON, NutritionPriority.PROTEIN)
    assert r.protein_reward is True
    assert r.grocery_mode is GroceryMode.CHEAPEST
    assert r.slot_kcal[L] == 468  # 85% of 550
    cook_days = [o for o in r.day_overrides]
    assert cook_days and all(o.cook_minutes == 25 and o.mood is RecipeMood.SIMPLE for o in cook_days)
    no_goals = resolve_prep(answers(), SETTINGS, TODAY).request
    assert (no_goals.nutrition_priority, no_goals.protein_reward, no_goals.grocery_mode) == (
        None,
        False,
        None,
    )


def test_your_pantry_and_extras_for_this_plan():
    plan = resolve_prep(
        answers(
            pantry=[{"ingredient_id": 7, "include": False}],
            extras=[
                {"ingredient_id": 1, "status": "have", "quantity": "2", "unit": "lb"},
                {"ingredient_id": 2, "status": "have"},
                {
                    "ingredient_id": 3,
                    "status": "have",
                    "quantity": "1",
                    "unit": "count",
                    "save_to_pantry": True,
                },
                {"ingredient_id": 4, "status": "could_buy"},
            ],
            people=2,
        ),
        SETTINGS,
        TODAY,
    )
    r = plan.request
    assert [(x.ingredient_id, x.quantity, x.unit) for x in r.extra_lots] == [(1, Decimal(2), "lb")]
    assert r.have_unlimited == [2]
    assert [(x.ingredient_id, x.quantity) for x in plan.save_to_pantry] == [(3, Decimal(1))]
    assert r.pantry_off == [7]
    assert r.could_buy == [4] and r.only_buy_could_buy is False
    assert r.household_size == 2


def test_use_what_i_have_buys_only_the_could_buys_and_a_list_takes_your_budget():
    use = resolve_prep(
        answers(shopping="use_what_i_have", extras=[{"ingredient_id": 4, "status": "could_buy"}]),
        SETTINGS,
        TODAY,
    ).request
    assert (use.mode, use.only_buy_could_buy, use.topup_cents, use.could_buy) == (
        PlanningMode.INVENTORY,
        True,
        None,
        [4],
    )
    shop = resolve_prep(answers(shopping="make_a_list", budget_cents=4500), SETTINGS, TODAY).request
    assert (shop.mode, shop.budget_cents, shop.only_buy_could_buy) == (PlanningMode.SHOP, 4500, False)


def test_answers_that_cant_make_a_plan_say_what_to_change():
    with pytest.raises(PrepAnswersError, match="up to 14 portions"):
        resolve_prep(answers({"shape": "portions", "slot": "lunch", "portions": 15}), SETTINGS, TODAY)
    with pytest.raises(PrepAnswersError, match="Drink has no calories set"):
        resolve_prep(answers({"shape": "portions", "slot": "drink", "portions": 3}), SETTINGS, TODAY)
    with pytest.raises(PrepAnswersError, match="Pick the days"):
        resolve_prep(answers({"shape": "days", "day_count": 3, "slots": []}), SETTINGS, TODAY)


def test_protein_share_and_the_same_as_last_time_line():
    assert protein_target(SETTINGS, (L,)) == 31
    a = answers(
        {**_big("today")},
        goals=["high_protein", "cheap"],
        mood="simple",
        budget_cents=4500,
        extras=[{"ingredient_id": 9, "status": "could_buy"}],
    )
    plan = resolve_prep(a, SETTINGS, TODAY)
    assert summary(a, plan, {9: "chickpeas"}, TODAY) == (
        "Meal prep · 5 lunches from today · High protein, Cheap · Simple · one big cook day, today · "
        "shopping, $45 limit · + chickpeas (could buy)"
    )
