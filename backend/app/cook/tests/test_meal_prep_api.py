"""POST /cook/meal-prep (E4, 2b.5 deliverable 3; AC 1, 2, 8): your answers become a draft meal-prep plan
inside the request, streamed with the building steps in order, with 0 LLM calls when the seed library covers
it."""

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.tests.conftest import TODAY, ingredient_id
from app.db.models import CookSearch, InventoryItem, MealPlan

FIVE_LUNCHES_TODAY = {
    "shape": "portions",
    "slot": "lunch",
    "portions": 5,
    "start": "today",
    "cook_style": "big_day",
    "cook_day": "today",
}


def meal_prep(api: Any, **answers: Any) -> list[dict[str, Any]]:
    reply = api.post("/api/v1/cook/meal-prep", json={"mode": "prep", "allow_llm": False, **answers})
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in reply.text.splitlines() if line.strip()]


def plan_of(events: list[dict[str, Any]]) -> dict[str, Any]:
    result = events[-1]
    assert result["event"] == "result", result
    assert result["status"] == "succeeded", result.get("problem")
    plan: dict[str, Any] = result["plan"]
    return plan


def test_five_lunches_from_today_cooking_today(api: Any, seeded_db: Session) -> None:
    """AC 1: one batch, cooked today; the portion past the 3-day fridge window comes from the freezer; no LLM
    call (the seed library covers lunch)."""
    events = meal_prep(api, prep=FIVE_LUNCHES_TODAY)
    plan = plan_of(events)
    assert events[-1]["llm_call_count"] == 0
    assert plan["kind"] == "meal_prep" and plan["status"] == "draft"
    assert len(plan["batches"]) == 1
    (batch,) = plan["batches"]
    assert batch["cook_on"] == str(TODAY) and batch["portions"] == 5
    assert batch["freezer_friendly"] is True
    assert (batch["fridge_portions"], batch["freezer_portions"]) == (4, 1)
    assert batch["portions_display"] == "5 portions (4 fridge, 1 freezer)"
    meals = [m for d in plan["days"] for m in d["meals"]]
    assert [m["eat_on"] for m in meals] == [str(TODAY + timedelta(days=i)) for i in range(5)]
    assert [m["storage"] for m in meals] == ["fresh", "fridge", "fridge", "fridge", "freezer"]
    assert meals[-1]["source_display"] == "From the freezer, cooked Wed 14 · thaw Sat 17 night"
    days = {d["day"]: d for d in plan["days"]}
    assert days[str(TODAY + timedelta(days=3))]["thaw_notes"] == [
        f"Thaw tomorrow's lunch ({batch['title']}) in the fridge tonight."
    ]
    assert days[str(TODAY)]["freeze_today"] == [f"Freeze 1 portion of {batch['title']} once cooled."]
    for day in plan["days"][1:]:
        assert day["cook_note"] == "Nothing to cook, eating prepped meals"
    assert plan["header"] == "5 lunches · Wed 14 – Sun 18"


def test_the_building_steps_arrive_in_order(api: Any) -> None:
    """AC 8: constraints, candidates, (generating), solving, pricing, validating, with friendly words."""
    events = meal_prep(api, prep=FIVE_LUNCHES_TODAY)
    stages = [e["stage"] for e in events if e["event"] == "progress"]
    order = ["constraints", "candidates", "solving", "pricing", "validating"]
    assert [s for s in stages if s in order] == order
    words = {e["stage"]: e["message"] for e in events if e["event"] == "progress"}
    assert words["constraints"] == "Checking your pantry"
    assert words["solving"] == "Balancing calories across the days"
    assert words["pricing"] == "Pricing your groceries"
    assert words["validating"] == "Double-checking every number"


def test_a_household_of_two_doubles_the_portions(api: Any) -> None:
    """AC 2: a meal is two portions from one batch; calories and protein are per person, and the plan passed
    the validator (it was saved)."""
    two = plan_of(meal_prep(api, prep=FIVE_LUNCHES_TODAY, people=2))
    assert two["household_size"] == 2
    meals = [m for d in two["days"] for m in d["meals"]]
    assert len(meals) == 5
    for batch in two["batches"]:
        eaten = sum(1 for m in meals if m["cook_batch_id"] == batch["id"])
        assert batch["portions"] == 2 * eaten + batch["portions_to_freeze"]
    assert all(d["kcal"] <= d["kcal_target"] + 150 for d in two["days"])  # your portion's calories


def test_answers_that_cant_make_a_plan_are_a_422_before_the_stream(api: Any) -> None:
    reply = api.post(
        "/api/v1/cook/meal-prep",
        json={"mode": "prep", "prep": {"shape": "portions", "slot": "drink", "portions": 3}},
    )
    assert reply.status_code == 422
    assert reply.json()["detail"] == "Drink has no calories set. Set them in Settings, Meals."


def test_save_to_pantry_and_same_as_last_time(api: Any, seeded_db: Session) -> None:
    eggs = ingredient_id(seeded_db, "egg-large")
    meal_prep(
        api,
        prep=FIVE_LUNCHES_TODAY,
        extras=[
            {
                "ingredient_id": eggs,
                "status": "have",
                "quantity": "12",
                "unit": "count",
                "save_to_pantry": True,
            }
        ],
    )
    lot = seeded_db.scalars(select(InventoryItem).where(InventoryItem.ingredient_id == eggs)).one()
    assert lot.quantity == 12
    search = seeded_db.scalars(select(CookSearch).where(CookSearch.mode == "prep")).one()
    assert (
        search.status == "done" and search.meal_plan_id is not None and search.generation_run_id is not None
    )
    assert seeded_db.get(MealPlan, search.meal_plan_id).kind == "meal_prep"  # type: ignore[union-attr]
    home = api.get("/api/v1/cook/home").json()
    prep = next(item for item in home["last"] if item["mode"] == "prep")
    assert prep["summary"] == (
        "Meal prep · 5 lunches from today · one big cook day, today · shopping · + egg, large (have it)"
    )


def test_two_lunches_still_have_room_between_the_week_floor_and_ceiling(api: Any) -> None:
    """A short plan's week window (3% of 1,100 kcal is 33 kcal) is narrower than the solver's usual rounding
    margins (20 kcal each side), which used to close it: the margins now take at most a quarter of it."""
    plan = plan_of(
        meal_prep(api, prep={"shape": "portions", "slot": "lunch", "portions": 2, "start": "today"})
    )
    assert 1067 <= plan["kcal_planned_week"] <= 1100
