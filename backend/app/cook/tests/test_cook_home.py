"""GET /cook/home (E1) and the Saved lists with pantry coverage (E9), step 2b.3a."""

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.cook.tests.conftest import NOW, ZONE, add_stock, final, ingredient_id, meal_now, results
from app.db.models import Recipe


def home(api: Any) -> dict[str, Any]:
    reply = api.get("/api/v1/cook/home")
    assert reply.status_code == 200, reply.text
    body: dict[str, Any] = reply.json()
    return body


def recipe_id(session: Any, title: str) -> int:
    return int(session.scalars(select(Recipe.id).where(Recipe.title == title)).one())


def test_a_first_visit_has_nothing_to_repeat_no_plan_and_nothing_saved(api):
    body = home(api)
    assert body == {
        "last": [],
        "today": None,
        "favorites": [],
        "favorites_count": 0,
        "later": [],
        "later_count": 0,
    }


def test_same_as_last_time_says_what_sending_the_answers_again_would_do(api, seeded_db):
    chickpeas = ingredient_id(seeded_db, "chickpeas-canned")
    thigh = ingredient_id(seeded_db, "chicken-thigh-boneless-skinless")
    answers = {
        "slot": "dinner",
        "goals": ["quick"],
        "extras": [{"ingredient_id": chickpeas, "status": "could_buy"}],
        "pantry": [{"ingredient_id": thigh, "include": False}],
    }
    events = meal_now(api, **answers)
    (last,) = home(api)["last"]
    assert last["mode"] == "now" and last["search_id"] == final(events)["search_id"]
    assert last["summary"] == (
        "A meal now · Dinner for 1 · Quick (30 min) · + chickpeas, canned, drained (could buy)"
        " · 1 pantry item off"
    )
    assert last["answers"]["goals"] == ["quick"]  # exactly as sent, to send again
    again = meal_now(api, **{k: v for k, v in last["answers"].items() if k != "schema_version"})
    assert final(again)["cached"] is True


def test_the_latest_search_wins_and_a_clock_meal_is_named_for_now(api, clock):
    meal_now(api, slot="lunch")
    meal_now(api)  # no meal: 18:30 is dinner
    (last,) = home(api)["last"]
    assert last["summary"] == "A meal now · Dinner for 1"
    clock(NOW.replace(hour=8))
    assert home(api)["last"][0]["summary"] == "A meal now · Breakfast for 1"  # what a tap would do now


def _plan_from_today(api: Any) -> int:
    reply = api.post(
        "/api/v1/plans", json={"week_start": NOW.date().isoformat(), "days": 3, "allow_llm": False}
    )
    lines = [json.loads(line) for line in reply.text.splitlines() if line.strip()]
    assert lines[-1]["status"] == "succeeded", lines[-1]
    plan_id = int(lines[-1]["plan_id"])
    assert api.post(f"/api/v1/plans/{plan_id}/accept").status_code == 200
    return plan_id


def test_the_today_card_shows_todays_meals_then_says_when_the_plan_starts_or_ended(api, clock):
    plan_id = _plan_from_today(api)
    today = home(api)["today"]
    assert (
        today["plan_id"] == plan_id and today["state"] == "today" and today["day"] == NOW.date().isoformat()
    )
    assert today["meals"] and all(m["dish_category"] for m in today["meals"])
    assert (
        today["cook_note"].startswith("Cook: ")
        or today["cook_note"] == "Nothing to cook, eating prepped meals"
    )
    clock(NOW - timedelta(days=2))  # Monday: the plan starts on Wednesday
    early = home(api)["today"]
    assert early["state"] == "starts_later" and early["message"] == "Your plan starts Wednesday"
    clock(datetime(2026, 10, 18, 9, 0, tzinfo=ZONE))  # Sunday: the 3-day plan ended on Friday
    late = home(api)["today"]
    assert late["state"] == "ended" and late["message"] == "Your plan ended Friday"


def test_saved_previews_are_most_recent_first_with_counts(api, seeded_db):
    curry = recipe_id(seeded_db, "Everyday chicken curry gravy")
    oats = recipe_id(seeded_db, "Chocolate protein overnight oats")
    api.put(f"/api/v1/recipes/{curry}/favorite")
    api.put(f"/api/v1/recipes/{oats}/favorite")
    api.put(f"/api/v1/recipes/{curry}/saved")
    body = home(api)
    assert body["favorites_count"] == 2 and body["later_count"] == 1
    assert {f["recipe_id"] for f in body["favorites"]} == {curry, oats}
    assert body["later"][0]["recipe_id"] == curry and body["later"][0]["dish_category"] == "curry"


def test_saved_cards_show_coverage_against_your_pantry_at_your_households_portions(api, seeded_db):
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 1000)
    curry = recipe_id(seeded_db, "Everyday chicken curry gravy")
    api.put(f"/api/v1/recipes/{curry}/favorite")
    api.patch("/api/v1/settings", json={"household_size": 2})
    (card,) = api.get("/api/v1/recipes/saved", params={"list": "favorites"}).json()
    assert card["uses"] == ["chicken thigh, boneless skinless"]
    assert card["could_buy"] == [] and card["missing"]
    assert (
        card["portions"] == 2
        and card["portions_display"] == "for 2 people"
        and card["badges"][0] == "favorite"
    )
    page = api.get(
        f"/api/v1/recipe-versions/{card['version_id']}",
        params={"portions": 2, "portion_size": card["portion_size"]},
    ).json()
    assert card["numbers"][0] == f"{page['per_portion']['kcal']} kcal"
    # the same card in a meal-now search for two
    now_card = next(c for c in results(meal_now(api, slot="dinner")) if c["recipe_id"] == curry)
    assert now_card["numbers"] == card["numbers"] and now_card["uses"] == card["uses"]
