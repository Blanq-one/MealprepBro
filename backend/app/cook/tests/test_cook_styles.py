"""How do you want to cook? (H5, FLOW_SPEC C1b; 2b.5 deliverables 7, 8, 10, 12; AC 10–13): one big cook day,
a few sessions, same dish for many portions, and mix it up, end to end through POST /cook/meal-prep. The
whole-week test uses a small seed pool so it solves to optimality (K6)."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.cook.prep import resolve_prep
from app.cook.tests.conftest import TODAY
from app.cook.tests.test_meal_prep_api import meal_prep, plan_of
from app.db.models import Recipe
from app.planning.orchestrator import Orchestrator
from app.schemas.cook import CookAnswers
from app.schemas.plans import PlanRequest
from app.services.settings import current_user, load_settings
from app.testing.llm import FakeClock, make_settings

POOL = {
    "Air-fryer chicken over rice with broccoli",
    "Egg fried rice with peas and carrots",
    "Chicken chana masala with rice",
    "Chicken, broccoli and pepper stir-fry",
    "Ground turkey tacos",
}


def keep_only(session: Session, titles: set[str]) -> None:
    session.execute(update(Recipe).where(Recipe.title.notin_(titles)).values(archived_at=Recipe.created_at))
    session.flush()


def whole_week(minutes: int) -> dict[str, Any]:
    return {
        "shape": "days",
        "day_count": 7,
        "slots": ["lunch", "dinner"],
        "start": "today",
        "cook_style": "big_day",
        "cook_day": "today",
        "cook_minutes": minutes,
    }


def test_a_whole_week_of_lunch_and_dinner_on_one_big_cook_day(api: Any, seeded_db: Session) -> None:
    """AC 10: every batch on that day, its hands-on total within that day's minutes; every portion past the
    fridge window comes from the freezer, from a recipe that freezes well, and its day says to thaw it the
    night before. Days without cooking say so; prep notes count their items."""
    keep_only(seeded_db, POOL)
    plan = plan_of(meal_prep(api, prep=whole_week(300)))
    assert {b["cook_on"] for b in plan["batches"]} == {str(TODAY)}
    today = plan["days"][0]
    assert today["day"] == str(TODAY) and 0 < today["hands_on_minutes"] <= 300
    assert today["cook_minutes_available"] == 300
    batches = {b["id"]: b for b in plan["batches"]}
    days = {d["day"]: d for d in plan["days"]}
    for day in plan["days"]:
        for meal in day["meals"]:
            eaten = date.fromisoformat(meal["eat_on"])
            past = eaten > TODAY + timedelta(days=3)
            assert meal["from_freezer"] is past
            assert meal["storage"] == ("freezer" if past else "fresh" if eaten == TODAY else "fridge")
            if past:
                assert batches[meal["cook_batch_id"]]["freezer_friendly"]
                before = days[str(eaten - timedelta(days=1))]
                assert any(meal["title"] in note for note in before["thaw_notes"])
        if day["day"] != str(TODAY):
            assert day["cook_note"] == "Nothing to cook, eating prepped meals"
    assert sum(b["freezer_portions"] for b in plan["batches"]) == 6  # lunch and dinner on days 5–7
    assert len(today["freeze_today"]) == len([b for b in plan["batches"] if b["freezer_portions"]])
    notes = plan["prep_notes"]
    assert notes is not None
    counts = {
        kind: sum(1 for i in notes["items"] if i["kind"] == kind)
        for kind in ("freeze", "freeze_portions", "spoil", "about")
    }
    expected = []
    if counts["freeze"] + counts["freeze_portions"]:
        expected.append(f"{counts['freeze'] + counts['freeze_portions']} to freeze")
    if counts["spoil"]:
        expected.append(f"{counts['spoil']} may spoil")
    if counts["about"]:  # the plan's own notes (recipes left out), behind the same row (2b.7, F23)
        expected.append("About this plan")
    assert notes["display"] == " · ".join(expected)
    # the batch view (F23): each batch says where its portions go, the freezer ones counted
    for b in plan["batches"]:
        meals = [m for d in plan["days"] for m in d["meals"] if m["cook_batch_id"] == b["id"]]
        assert [u["label"] for u in b["uses"]] == [
            f"{date.fromisoformat(m['eat_on']):%a} {m['slot'].replace('protein_dessert', 'dessert')}"
            for m in meals
        ]
        if b["freezer_portions"]:
            assert b["uses_display"].endswith(f"({b['freezer_portions']} to the freezer)")
    if plan["batches"]:  # the cook day's timeline (step 2b.9), from 0:00 to Done
        assert today["timeline"][0]["at_display"] == "0:00" and today["timeline"][-1]["text"] == "Done"
        assert today["time_display"].startswith("about ")


def test_too_few_minutes_on_the_big_day_gives_the_time_fix(api: Any, seeded_db: Session) -> None:
    keep_only(seeded_db, POOL)
    result = meal_prep(api, prep=whole_week(40))[-1]
    assert result["status"] == "infeasible"
    fixes = [d for d in result["problem"]["diagnostics"] if d.get("suggested_minutes")]
    assert fixes and fixes[0]["suggested_minutes"] > 40
    assert fixes[0]["message"].startswith("Wednesday needs ")


def test_same_dish_for_8_portions_is_one_batch_above_the_weekly_cap(api: Any) -> None:
    """AC 11: one batch of one recipe at 8 portions (the 5-portion cap is lifted, F22): the 4 within the
    fridge window stay in the fridge, the rest are frozen."""
    plan = plan_of(
        meal_prep(
            api,
            prep={
                "shape": "portions",
                "slot": "dinner",
                "portions": 8,
                "cook_style": "same_dish",
                "cook_day": "today",
            },
        )
    )
    (batch,) = plan["batches"]
    assert batch["portions"] == 8 and batch["cook_on"] == str(TODAY)
    assert (batch["fridge_portions"], batch["freezer_portions"]) == (4, 4)
    assert batch["freezer_friendly"] is True
    assert {m["recipe_version_id"] for d in plan["days"] for m in d["meals"]} == {batch["recipe_version_id"]}


def test_same_dish_past_the_fridge_window_needs_a_recipe_that_freezes_well(
    api: Any, seeded_db: Session
) -> None:
    keep_only(seeded_db, {"Lemon garlic salmon with rice and broccoli"})  # doesn't freeze well
    result = meal_prep(
        api,
        prep={
            "shape": "portions",
            "slot": "dinner",
            "portions": 8,
            "cook_style": "same_dish",
            "cook_day": "today",
        },
    )[-1]
    assert result["status"] == "infeasible"


def test_a_few_sessions_cook_only_on_the_chosen_days(api: Any) -> None:
    """AC 12: batches only on the session days, each within its own minutes. Raw protein bought today and
    cooked on Saturday is frozen on shopping day, and that step shows on today's card too."""
    saturday = TODAY + timedelta(days=3)
    plan = plan_of(
        meal_prep(
            api,
            prep={
                "shape": "days",
                "day_count": 7,
                "slots": ["dinner"],
                "cook_style": "sessions",
                "sessions": [{"day": str(TODAY), "minutes": 40}, {"day": str(saturday), "minutes": 40}],
            },
        )
    )
    assert {b["cook_on"] for b in plan["batches"]} <= {str(TODAY), str(saturday)}
    for day in plan["days"]:
        assert day["hands_on_minutes"] <= day["cook_minutes_available"]
        if day["day"] not in (str(TODAY), str(saturday)):
            assert day["cook_minutes_available"] == 0
    shopping_day = plan["days"][0]
    assert shopping_day["freeze_steps"] == [f["message"] for f in plan["freeze"]]
    if plan["freeze"]:
        assert plan["prep_notes"] is not None
        freeze_items = [i["text"] for i in plan["prep_notes"]["items"] if i["kind"] == "freeze"]
        assert freeze_items == shopping_day["freeze_steps"]


def test_mix_it_up_plans_exactly_like_todays_planner(seeded_db: Session) -> None:
    """AC 12: "mix it up" for all your meals is the same request your settings make for POST /plans."""
    user = current_user(seeded_db)
    answers = CookAnswers.model_validate(
        {
            "mode": "prep",
            "allow_llm": False,
            "prep": {
                "shape": "days",
                "day_count": 3,
                "slots": ["breakfast", "lunch", "dinner", "protein_dessert"],
                "cook_style": "mix",
            },
        }
    )
    request = resolve_prep(answers, load_settings(seeded_db, user.id), TODAY).request

    def run(r: PlanRequest) -> Any:
        o = Orchestrator(
            seeded_db, user.id, llm_client=None, settings=make_settings(), clock=FakeClock(), today=TODAY
        )
        out = o.run(r)
        assert out.status == "succeeded", out.error
        return out.plan

    prep = run(request)
    plain = run(PlanRequest(week_start=TODAY, days=3, allow_llm=False))
    assert prep.constraints.content_hash() == plain.constraints.content_hash()
    assert [(m.eat_on, m.slot, prep.batches[m.batch_index].version_id) for m in prep.meals] == [
        (m.eat_on, m.slot, plain.batches[m.batch_index].version_id) for m in plain.meals
    ]
