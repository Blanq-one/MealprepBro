"""Step 2b.4 AC 1: the meal-now screens' calls, in the order the app makes them, against the real backend
(seed and saved recipes only, no LLM): Cook home → the add flow → Find recipes → a card's recipe page →
Cook this → Buy first → cooking mode → Mark cooked → Cook home again."""

from decimal import Decimal
from typing import Any

from app.cook.tests.conftest import add_stock, ingredient_id, meal_now, results
from app.db.models import InventoryItem


def ok(reply: Any, status: int = 200) -> Any:
    assert reply.status_code == status, reply.text
    return reply.json()


def test_a_meal_now_from_cook_home_to_mark_cooked(api, seeded_db):
    thigh = add_stock(seeded_db, "chicken-thigh-boneless-skinless", 1000)
    rice = add_stock(seeded_db, "rice-long-grain-white", 2000)
    home = ok(api.get("/api/v1/cook/home"))
    assert home["last"] == [] and home["portions"] == 1

    # "What do you have?": add frozen spinach with Not sure (saved to Pantry), and chickpeas as could buy
    spinach = ingredient_id(seeded_db, "spinach-frozen")
    options = ok(api.get(f"/api/v1/ingredients/{spinach}/add-options"))
    assert options["food"] == "Spinach" and {f["form"] for f in options["forms"]} == {"fresh", "frozen"}
    (lot,) = ok(
        api.post(
            "/api/v1/inventory/bulk",
            json={"items": [{"ingredient_id": spinach, "not_sure": True, "location": "freezer"}]},
        ),
        201,
    )
    assert lot["quantity_is_estimate"] is True and lot["container"] == "box"

    # Find recipes: rice turned off for this search; chickpeas could buy
    chickpeas = ingredient_id(seeded_db, "chickpeas-canned")
    answers = {
        "goals": ["high_protein"],
        "pantry": [{"ingredient_id": rice.ingredient_id, "include": False}],
        "extras": [{"ingredient_id": chickpeas, "status": "could_buy"}],
        "slot": "dinner",
    }
    events = meal_now(api, **answers)
    assert events[0]["event"] == "started" and events[-1]["event"] == "result"
    search_id = events[-1]["search_id"]
    cards = results(events)
    assert cards, "seed recipes fill the results"
    stored = ok(api.get(f"/api/v1/cook/searches/{search_id}"))  # the results page after the stream
    assert [c["version_id"] for c in stored["suggestions"]] == [c["version_id"] for c in cards]

    # a card's recipe page, at the card's portions, with this search's lines
    card = next(c for c in cards if "chicken thigh, boneless skinless" in c["uses"])
    page = ok(api.get(f"/api/v1/recipe-versions/{card['version_id']}", params={"search": search_id}))
    assert page["portions"] == card["portions"] and page["search_context"]["search_id"] == search_id
    notes = {ln["ingredient_id"]: ln["note"] for ln in page["search_context"]["lines"]}
    assert notes[thigh.ingredient_id].startswith("uses ")

    # Cook this → Buy first (when something is to buy) → cooking mode → Mark cooked
    out = ok(
        api.post("/api/v1/cook/meals", json={"version_id": card["version_id"], "search_id": search_id}), 201
    )
    if out["buy_first"]:
        trip = ok(api.get(f"/api/v1/plans/{out['plan_id']}/grocery-list", params={"group_by": "store"}))
        to_buy = [i for g in trip["groups"] for i in g["items"] if i["kind"] == "buy"]
        for item in to_buy:
            ok(api.patch(f"/api/v1/grocery-items/{item['id']}", json={"checked": True}))
        ok(api.post(f"/api/v1/grocery-lists/{out['grocery_list_id']}/complete", json={}))
    batch = ok(api.get(f"/api/v1/cook-batches/{out['batch_id']}"))
    assert batch["recipe"]["steps"] and batch["status"] == "planned"
    before = seeded_db.get(InventoryItem, thigh.id).quantity
    cooked = ok(api.post(f"/api/v1/cook-batches/{out['batch_id']}/cooked", json={}))
    assert cooked["status"] == "cooked"
    seeded_db.refresh(thigh)
    seeded_db.refresh(rice)
    assert thigh.quantity < before  # it came from your thighs
    assert rice.quantity == Decimal(2000)  # turned off for this search: never touched
    assert api.post(f"/api/v1/cook-batches/{out['batch_id']}/cooked", json={}).status_code == 409

    # back on Cook home: Same as last time, with last time's extras for the chips
    home = ok(api.get("/api/v1/cook/home"))
    (last,) = home["last"]
    assert last["search_id"] == search_id and last["extras"] == [
        {"ingredient_id": chickpeas, "name": "chickpeas, canned, drained", "status": "could_buy"}
    ]
