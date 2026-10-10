"""Step 2b.4 additions: versions of held items (J4), forms and package presets (J5), and recipe amounts in
your terms (J6)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.cook.caps import meals_this_week
from app.cook.tests.conftest import (
    TODAY,
    add_recipe,
    add_stock,
    final,
    ingredient_id,
    meal_now,
    results,
    titles,
)
from app.cook.your_terms import PantryLot, amount_text, note
from app.db.models import IngredientPreference, InventoryItem
from app.services.exclusions import diet_status
from app.services.ingredient_data import load_by_slug
from app.services.settings import current_user

PORK_CHOP = [("pork-chop-boneless", 300, "g", "protein"), ("rice-long-grain-white", 75, "g", "carb")]


def options(api: Any, session: Any, slug: str) -> dict[str, Any]:
    reply = api.get(f"/api/v1/ingredients/{ingredient_id(session, slug)}/add-options")
    assert reply.status_code == 200, reply.text
    body: dict[str, Any] = reply.json()
    return body


def bulk(api: Any, *items: dict[str, Any]) -> Any:
    return api.post("/api/v1/inventory/bulk", json={"items": list(items)})


# ---------------- J4: versions of held items ----------------
def test_a_held_item_with_versions_asks_which_version_with_label_guidance(api, seeded_db):
    body = options(api, seeded_db, "pepperoni")
    assert body["state"] == "held" and "Pick the version on its label" in body["message"]
    versions = body["versions"]
    assert versions["question"] == "Which pepperoni is it?" and versions["guidance"].startswith(
        "Check the label"
    )
    states = {c["key"]: (c["state"], c["note"]) for c in versions["choices"]}
    assert states["pork_beef"] == ("excluded", "Off your list: it contains beef")
    assert states["pork"][0] == "capped" and "pork as a meal component" in states["pork"][1]
    assert states["turkey"] == ("allowed", "Allowed") and states["chicken"] == ("allowed", "Allowed")
    assert states["not_sure"] == ("held", "Stays held until you check the label")
    estimated = {c["key"] for c in versions["choices"] if c["nutrition_estimated"]}
    assert estimated == {"pork", "chicken"}  # USDA has no exact pork-only or chicken pepperoni
    bouillon = options(api, seeded_db, "chicken-bouillon-cube")["versions"]
    assert [c["key"] for c in bouillon["choices"]] == ["no_beef", "with_beef", "not_sure"]
    assert [c["state"] for c in bouillon["choices"]] == ["allowed", "excluded", "held"]


def test_turkey_pepperoni_never_counts_toward_the_pork_cap(api, seeded_db):
    user = current_user(seeded_db)
    pizza = add_recipe(
        seeded_db,
        "Turkey pepperoni flatbread",
        [("pepperoni-turkey", 60, "g", "protein"), ("pita", 2, "count", "carb")],
    )
    pork = add_recipe(seeded_db, "Pork chop with rice", PORK_CHOP)
    cooked = api.post("/api/v1/cook/meals", json={"version_id": pizza.id, "slot": "dinner"})
    assert cooked.status_code == 201, cooked.text
    caps = diet_status(seeded_db, user.id).caps
    assert meals_this_week(seeded_db, user.id, caps, TODAY) == {"Pork as a meal component": 0}
    # this week's pork meal still allowed, and the turkey pepperoni recipe is never treated as pork
    cards = results(meal_now(api, slot="dinner"))
    assert {pizza.title, pork.title} <= set(titles(cards))
    api.post("/api/v1/cook/meals", json={"version_id": pork.id, "slot": "dinner"})  # uses the allowance
    cards = {c["title"]: c for c in results(meal_now(api, slot="dinner"))}
    assert pork.title not in cards and pizza.title in cards


def test_pork_and_beef_pepperoni_is_always_excluded(api, seeded_db):
    beefy = ingredient_id(seeded_db, "pepperoni-pork-beef")
    recipe = add_recipe(
        seeded_db, "Pork and beef pepperoni flatbread", [("pepperoni-pork-beef", 60, "g", "protein")]
    )
    # allowing it changes nothing: an allow never overrides beef
    api.put(f"/api/v1/settings/ingredient-preferences/{beefy}", json={"preference": "allow"})
    assert options(api, seeded_db, "pepperoni-pork-beef")["state"] == "excluded"
    events = meal_now(api, slot="dinner")
    assert recipe.title not in titles(results(events))
    reply = bulk(api, {"ingredient_id": beefy, "preset": "6oz", "location": "fridge"})
    assert reply.status_code == 422 and "excluded" in reply.json()["detail"]
    assert api.post("/api/v1/cook/meals", json={"version_id": recipe.id, "slot": "dinner"}).status_code == 422


def test_choosing_a_version_never_releases_the_generic_held_item(api, seeded_db):
    generic = ingredient_id(seeded_db, "pepperoni")
    turkey = ingredient_id(seeded_db, "pepperoni-turkey")
    lot = add_stock(seeded_db, "pepperoni", 170)  # a held item can sit in your pantry
    reply = api.post(f"/api/v1/inventory/{lot.id}/version", json={"ingredient_id": turkey})
    assert reply.status_code == 200, reply.text
    new = reply.json()
    assert new["ingredient_id"] == turkey and Decimal(new["quantity"]) == Decimal(170)
    seeded_db.refresh(lot)
    assert lot.status == "depleted" and lot.quantity == 0
    held = {d["ingredient_id"]: d["decision"] for d in api.get("/api/v1/settings").json()["diet_review"]}
    assert held[generic] == "held"
    assert seeded_db.get(IngredientPreference, (current_user(seeded_db).id, generic)) is None
    # only one of its versions, and only for a held item with versions
    other = add_stock(seeded_db, "pepperoni", 100)
    wrong = api.post(
        f"/api/v1/inventory/{other.id}/version", json={"ingredient_id": ingredient_id(seeded_db, "bacon")}
    )
    assert wrong.status_code == 422


# ---------------- J5: forms and package presets ----------------
def test_a_food_with_forms_offers_each_form_with_its_presets(api, seeded_db):
    body = options(api, seeded_db, "cauliflower-frozen")
    assert body["food"] == "Cauliflower" and body["selected_form"] == "frozen"
    forms = {f["form"]: f for f in body["forms"]}
    assert set(forms) == {"fresh", "frozen"}
    assert [p["label"] for p in forms["frozen"]["presets"]] == ["10 oz bag", "12 oz bag", "16 oz bag"]
    assert next(p for p in forms["frozen"]["presets"] if p["default"])["label"] == "12 oz bag"
    assert [p["label"] for p in forms["fresh"]["presets"]] == [
        "small head (about 1.5 lb)",
        "medium head (about 2 lb)",
        "large head (about 3 lb)",
    ]
    assert forms["frozen"]["location"] == "freezer" and forms["fresh"]["location"] == "fridge"
    assert all(p["is_estimate"] for f in forms.values() for p in f["presets"])
    assert [u["unit"] for u in forms["frozen"]["custom_units"]][:2] == ["lb", "oz"]
    single = options(api, seeded_db, "garlic")
    assert single["food"] is None and [f["form"] for f in single["forms"]] == ["as_is"]


def test_a_preset_adds_its_package_and_a_frozen_form_keeps_for_months(api, seeded_db):
    frozen = ingredient_id(seeded_db, "cauliflower-frozen")
    fresh = ingredient_id(seeded_db, "cauliflower")
    reply = bulk(
        api,
        {"ingredient_id": frozen, "preset": "16oz", "location": "freezer"},
        {"ingredient_id": fresh, "preset": "medium", "location": "fridge"},
    )
    assert reply.status_code == 201, reply.text
    bag, head = reply.json()
    assert Decimal(bag["quantity"]) == Decimal("453.592") and bag["unit"] == "g"
    assert bag["container"] == "bag" and bag["quantity_is_estimate"] is False
    added = datetime.now(UTC).date()  # the bulk add starts its use-by estimate today
    assert bag["expires_on"] == (added + timedelta(days=240)).isoformat()  # about 8 months frozen
    assert head["expires_on"] is None  # fresh cauliflower: no shelf life on file, so no date
    assert head["container"] == "head" and Decimal(head["quantity"]) == Decimal("907.185")
    assert bulk(api, {"ingredient_id": frozen, "preset": "nope", "location": "freezer"}).status_code == 422


def test_not_sure_adds_the_usual_size_marked_as_an_estimate_until_you_correct_it(api, seeded_db):
    frozen = ingredient_id(seeded_db, "cauliflower-frozen")
    (lot,) = bulk(api, {"ingredient_id": frozen, "not_sure": True, "location": "freezer"}).json()
    assert lot["quantity_is_estimate"] is True and Decimal(lot["quantity"]) == Decimal("340.194")  # 12 oz
    fixed = api.patch(f"/api/v1/inventory/{lot['id']}", json={"quantity": "283.495"}).json()
    assert fixed["quantity_is_estimate"] is False and Decimal(fixed["quantity"]) == Decimal("283.495")
    both = {"ingredient_id": frozen, "not_sure": True, "preset": "16oz", "location": "freezer"}
    assert bulk(api, both).status_code == 422


def test_pantry_corrects_an_estimate_by_package_or_custom_amount_and_the_server_converts(api, seeded_db):
    frozen = ingredient_id(seeded_db, "cauliflower-frozen")
    (lot,) = bulk(api, {"ingredient_id": frozen, "not_sure": True, "location": "freezer"}).json()
    by_preset = api.patch(f"/api/v1/inventory/{lot['id']}", json={"preset": "16oz"})
    assert by_preset.status_code == 200, by_preset.text
    fixed = by_preset.json()
    assert fixed["quantity_is_estimate"] is False and Decimal(fixed["quantity"]) == Decimal("453.592")
    (lot,) = bulk(api, {"ingredient_id": frozen, "not_sure": True, "location": "freezer"}).json()
    custom = api.patch(f"/api/v1/inventory/{lot['id']}", json={"quantity": "0.75", "unit": "lb"}).json()
    assert custom["quantity_is_estimate"] is False and Decimal(custom["quantity"]) == Decimal("340.194")
    wrong = api.patch(f"/api/v1/inventory/{lot['id']}", json={"quantity": "2", "unit": "count"})
    assert wrong.status_code == 422  # a bag of florets is weighed, not counted
    both = api.patch(f"/api/v1/inventory/{lot['id']}", json={"preset": "16oz", "quantity": "1"})
    assert both.status_code == 422


def test_settings_lists_the_versions_of_held_items(api, seeded_db):
    review = {d["name"]: d for d in api.get("/api/v1/settings").json()["diet_review"]}
    pepperoni = next(d for name, d in review.items() if name.startswith("pepperoni"))
    assert pepperoni["decision"] == "held"
    keys = [c["key"] for c in pepperoni["versions"]["choices"]]
    assert keys == ["pork_beef", "pork", "turkey", "chicken", "not_sure"]
    assert pepperoni["versions"]["guidance"].startswith("Check the label")
    plain = [d for d in review.values() if d["versions"] is None]
    assert plain  # held items without versions (gelatin of unknown source) list none


def test_a_recipe_opened_from_a_search_starts_at_that_cards_portions(api, seeded_db):
    events = meal_now(api, slot="dinner", people=2)
    card = results(events)[0]
    page = api.get(
        f"/api/v1/recipe-versions/{card['version_id']}", params={"search": final(events)["search_id"]}
    ).json()
    assert page["portions"] == card["portions"] == 2
    assert page["search_context"]["portions_display"] == card["portions_display"]
    home = api.get("/api/v1/cook/home").json()
    assert (home["portions"], home["portion_size"]) == (1, "normal")  # saved cards open for your household


def test_a_have_it_extra_with_its_amount_is_counted_like_stock(api, seeded_db):
    thigh = ingredient_id(seeded_db, "chicken-thigh-boneless-skinless")
    events = meal_now(
        api,
        slot="dinner",
        extras=[{"ingredient_id": thigh, "status": "have", "quantity": "100", "unit": "g"}],
    )
    curry = next(c for c in results(events) if c["title"] == "Everyday chicken curry gravy")
    assert curry["uses"] == ["chicken thigh, boneless skinless (some)"]  # 100 g of about 170 g


# ---------------- J6: recipe amounts in your terms ----------------
def test_the_recipe_page_says_what_it_uses_of_your_bag_and_mark_cooked_takes_exactly_that(api, seeded_db):
    broccoli = ingredient_id(seeded_db, "broccoli-frozen")
    bowl = add_recipe(
        seeded_db,
        "Broccoli rice bowl",
        [("broccoli-frozen", "226.796", "g", "vegetable"), ("rice-long-grain-white", 75, "g", "carb")],
        servings=1,
    )
    (bag,) = bulk(api, {"ingredient_id": broccoli, "preset": "16oz", "location": "freezer"}).json()
    events = meal_now(api, slot="dinner")
    card = next(c for c in results(events) if c["version_id"] == bowl.id)
    page = api.get(
        f"/api/v1/recipe-versions/{bowl.id}", params={"portions": 1, "search": final(events)["search_id"]}
    ).json()
    lines = {ln["ingredient_id"]: ln for ln in page["search_context"]["lines"]}
    expected = "uses 8 oz, about half your bag · 8 oz left after"
    assert lines[broccoli]["note"] == expected
    out = api.post(
        "/api/v1/cook/meals", json={"version_id": card["version_id"], "search_id": final(events)["search_id"]}
    )
    batch = api.get(f"/api/v1/cook-batches/{out.json()['batch_id']}").json()
    assert {n["ingredient_id"]: n["note"] for n in batch["pantry_notes"]}[broccoli] == expected
    api.post(f"/api/v1/cook-batches/{out.json()['batch_id']}/cooked", json={})
    left = seeded_db.get(InventoryItem, bag["id"])
    assert left.quantity == Decimal("226.796") and left.status == "active"  # the rest stays in Pantry
    assert api.get(f"/api/v1/cook-batches/{out.json()['batch_id']}").json()["pantry_notes"] == []


def test_notes_in_your_terms_for_counts_volumes_and_more_than_you_have(seeded_db):
    data = load_by_slug(seeded_db)
    eggs = data["egg-large"].units
    assert note(Decimal(2), "count", [PantryLot(1, Decimal(12), "count", "carton")], eggs) == (
        "uses 2 of your 12 · 10 left after"
    )
    milk = data["milk-2"].units
    assert note(Decimal("236.588"), "ml", [PantryLot(2, Decimal("1892.71"), "ml", "jug")], milk) == (
        "uses 1 cup, a little of your jug · 7 cups left after"
    )
    thigh = data["chicken-thigh-boneless-skinless"].units
    assert note(Decimal(700), "g", [PantryLot(3, Decimal(500), "g", "pack")], thigh) == (
        "uses all 1.1 lb you have (it needs 1.54 lb)"
    )
    two_lots = [PantryLot(4, Decimal(300), "g", "pack"), PantryLot(5, Decimal(300), "g", "pack")]
    assert (
        note(Decimal(150), "g", two_lots, thigh)
        == "uses 5.3 oz, about a quarter of what you have · 15.9 oz left after"
    )
    assert (
        amount_text(Decimal(1000), "g", "metric") == "1 kg"
        and amount_text(Decimal(113), "g", "metric") == "113 g"
    )
    assert note(Decimal(10), "g", [], thigh) is None
