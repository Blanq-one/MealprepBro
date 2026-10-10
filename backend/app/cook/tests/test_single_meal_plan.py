"""Cook this (E3), step 2b.3a AC 5: a one-meal plan validates, deducts inventory on Mark cooked, and never
becomes the current plan; your pantry choices and household size carry into it."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.cook.tests.conftest import NOW, add_recipe, add_stock, final, ingredient_id, meal_now, results
from app.db.models import MealPlan, PlanBatchIngredient


def card(events: list[dict[str, Any]], title: str) -> dict[str, Any]:
    return next(c for c in results(events) if c["title"] == title)


def cook(api: Any, **body: Any) -> Any:
    return api.post("/api/v1/cook/meals", json=body)


def grocery(api: Any, plan_id: int) -> dict[str, dict[str, Any]]:
    body = api.get(f"/api/v1/plans/{plan_id}/grocery-list").json()
    return {item["name"]: item for group in body["groups"] for item in group["items"]}


def test_cook_this_saves_a_valid_one_meal_plan_that_is_never_current(api, seeded_db):
    thigh = add_stock(seeded_db, "chicken-thigh-boneless-skinless", 1000)
    events = meal_now(api, slot="dinner")
    gravy = card(events, "Chicken and spinach gravy")
    reply = cook(api, version_id=gravy["version_id"], search_id=final(events)["search_id"])
    assert reply.status_code == 201, reply.text
    out = reply.json()
    plan = out["plan"]
    assert out["created"] and out["buy_first"]  # spinach, onion, tomato… to buy first
    assert plan["kind"] == "single" and plan["status"] == "draft"
    assert [d["day"] for d in plan["days"]] == [NOW.date().isoformat()]
    (day,) = plan["days"]
    (meal,) = day["meals"]
    assert meal["slot"] == "dinner" and meal["title"] == gravy["title"]
    assert f"{meal['kcal']} kcal" == gravy["numbers"][0]  # the card's numbers
    (batch,) = plan["batches"]
    assert batch["portions"] == 1 and batch["id"] == out["batch_id"]
    row = seeded_db.get(MealPlan, out["plan_id"])
    assert row.validation_report["ok"] is True and row.kind == "single"
    # never the current plan: not listed, not current, can't be accepted, no Today card
    assert all(p["id"] != out["plan_id"] for p in api.get("/api/v1/plans").json())
    assert api.post(f"/api/v1/plans/{out['plan_id']}/accept").status_code == 409
    assert api.get("/api/v1/cook/home").json()["today"] is None
    items = grocery(api, out["plan_id"])
    assert items["chicken thigh, boneless skinless"]["kind"] == "from_inventory"
    assert items["spinach, fresh"]["kind"] == "buy"
    # Mark cooked takes the thighs from your lot
    used = seeded_db.scalars(
        select(PlanBatchIngredient.quantity).where(
            PlanBatchIngredient.cook_batch_id == out["batch_id"],
            PlanBatchIngredient.ingredient_id == thigh.ingredient_id,
        )
    ).one()
    cooked = api.post(f"/api/v1/cook-batches/{out['batch_id']}/cooked", json={})
    assert cooked.status_code == 200, cooked.text
    seeded_db.refresh(thigh)
    assert thigh.quantity == Decimal(1000) - used
    assert api.post(f"/api/v1/cook-batches/{out['batch_id']}/cooked", json={}).status_code == 409


def test_cook_this_again_for_the_same_search_returns_that_plan_until_it_is_cooked(api, seeded_db):
    events = meal_now(api, slot="dinner")
    body = {"version_id": results(events)[0]["version_id"], "search_id": final(events)["search_id"]}
    first = cook(api, **body)
    again = cook(api, **body)
    assert again.status_code == 200 and again.json()["created"] is False
    assert again.json()["plan_id"] == first.json()["plan_id"]
    api.post(f"/api/v1/cook-batches/{first.json()['batch_id']}/cooked", json={})
    later = cook(api, **body)
    assert later.status_code == 201 and later.json()["plan_id"] != first.json()["plan_id"]


def test_a_household_of_two_eats_both_portions_of_one_meal(api, seeded_db):
    events = meal_now(api, slot="dinner", people=2)
    choice = results(events)[0]
    out = cook(api, version_id=choice["version_id"], search_id=final(events)["search_id"]).json()
    plan = out["plan"]
    (batch,) = plan["batches"]
    (meal,) = plan["days"][0]["meals"]
    assert batch["portions"] == 2 and f"{meal['kcal']} kcal" == choice["numbers"][0]  # your portion
    assert meal["cost_cents"] == batch["cost_cents"] == plan["costs"]["eaten_cents"]  # both portions eaten
    assert plan["costs"]["frozen_portions_cents"] == 0
    assert seeded_db.get(MealPlan, out["plan_id"]).validation_report["ok"] is True


def test_have_it_extras_and_turned_off_items_carry_into_the_plan(api, seeded_db):
    thigh = add_stock(seeded_db, "chicken-thigh-boneless-skinless", 1000)
    spinach = ingredient_id(seeded_db, "spinach")
    events = meal_now(
        api,
        slot="dinner",
        pantry=[{"ingredient_id": thigh.ingredient_id, "include": False}],
        extras=[{"ingredient_id": spinach, "status": "have"}],
    )
    gravy = card(events, "Chicken and spinach gravy")
    out = cook(api, version_id=gravy["version_id"], search_id=final(events)["search_id"]).json()
    items = grocery(api, out["plan_id"])
    assert "spinach, fresh" not in items  # yours for this meal: never listed
    assert items["chicken thigh, boneless skinless"]["kind"] == "buy"  # your thighs are off for this search
    row = seeded_db.get(MealPlan, out["plan_id"])
    assert spinach in row.constraints["always_have_ingredient_ids"]
    assert thigh.ingredient_id in row.constraints["lots_off_ingredient_ids"]
    assert row.validation_report["ok"] is True


def test_cook_this_without_a_search_uses_the_recipes_meal_and_your_household(api, seeded_db):
    oats = next(
        c
        for c in results(meal_now(api, slot="breakfast"))
        if c["title"] == "Chocolate protein overnight oats"
    )
    out = cook(api, version_id=oats["version_id"]).json()
    (meal,) = out["plan"]["days"][0]["meals"]
    assert meal["slot"] == "breakfast"  # 18:30 is dinner by the clock, but this is a breakfast recipe
    assert out["plan"]["batches"][0]["portions"] == 1


def test_a_recipe_your_rules_rule_out_is_refused(api, seeded_db):
    beef = add_recipe(seeded_db, "Beef skillet", [("ground-beef-85", 300, "g", "protein")])
    reply = cook(api, version_id=beef.id, slot="dinner")
    assert reply.status_code == 422 and "beef" in reply.json()["detail"].lower()
    pork = add_recipe(seeded_db, "Pork chop", [("pork-chop-boneless", 300, "g", "protein")])
    assert cook(api, version_id=pork.id, slot="dinner").status_code == 201
    second = cook(api, version_id=pork.id, slot="dinner")
    assert second.status_code == 422 and "allowance" in second.json()["detail"]
    assert cook(api, version_id=999999).status_code == 404
