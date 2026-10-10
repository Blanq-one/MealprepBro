"""Settings v3 (step 2b.1): the new fields, PATCH for a few fields ("Skip, use my current settings"),
POST /settings/preview (field errors and summary lines, nothing saved), and GET / POST /stores."""

import copy
import json

import pytest
from pydantic import ValidationError

from app.schemas.settings import UserSettings
from app.seed.files import DATA_DIR
from app.services import settings as service
from app.services.settings import current_user, load_settings

DEFAULTS = json.loads((DATA_DIR / "settings_default.json").read_text(encoding="utf-8"))
PROBLEM = "application/problem+json"


def _with(**changes):
    data = copy.deepcopy(DEFAULTS)
    data.update(changes)
    return data


def test_v3_defaults():
    settings = UserSettings.model_validate(DEFAULTS)
    assert settings.schema_version == 3
    assert (settings.household_size, settings.always_have, settings.default_budget_cents) == (1, [], None)
    assert settings.onboarding_completed is False  # so the wizard runs once, pre-filled


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"schema_version": 2}, "Input should be 3"),
        ({"household_size": 0}, "greater than or equal to 1"),
        ({"household_size": 9}, "less than or equal to 8"),
        ({"always_have": ["salt", "salt"]}, "always_have has duplicates"),
        ({"default_budget_cents": -1}, "greater than or equal to 0"),
    ],
)
def test_invalid_v3_fields(changes, message):
    with pytest.raises(ValidationError, match=message):
        UserSettings.model_validate(_with(**changes))


def test_get_settings_is_v3(client):
    body = client.get("/api/v1/settings").json()["settings"]
    assert body["schema_version"] == 3 and body["onboarding_completed"] is False
    assert body["household_size"] == 1 and body["always_have"] == []


def test_patch_with_only_the_onboarding_flag_changes_nothing_else(client, seeded_db):
    before = load_settings(seeded_db, current_user(seeded_db).id).model_dump(mode="json")
    reply = client.patch("/api/v1/settings", json={"onboarding_completed": True})
    assert reply.status_code == 200, reply.text
    after = reply.json()["settings"]
    assert after == {**before, "onboarding_completed": True}
    assert load_settings(seeded_db, current_user(seeded_db).id).onboarding_completed is True


def test_patch_validates_the_whole_result(client, seeded_db):
    reply = client.patch("/api/v1/settings", json={"household_size": 0})
    assert reply.status_code == 422 and reply.headers["content-type"] == PROBLEM
    assert reply.json()["errors"][0]["loc"] == ["household_size"]
    reply = client.patch("/api/v1/settings", json={"always_have": ["unicorn-dust"]})
    assert reply.status_code == 422 and "no ingredient with slug 'unicorn-dust'" in reply.json()["detail"]
    reply = client.patch("/api/v1/settings", json={"always_have": ["beef-broth"]})
    assert reply.status_code == 422 and "always excluded" in reply.json()["detail"]
    assert load_settings(seeded_db, current_user(seeded_db).id).always_have == []  # nothing saved


def test_always_have_and_a_default_budget_are_saved(client):
    reply = client.patch(
        "/api/v1/settings",
        json={"always_have": ["salt", "olive-oil", "rice-long-grain-white"], "default_budget_cents": 4500},
    )
    assert reply.status_code == 200, reply.text
    body = reply.json()["settings"]
    assert body["always_have"] == ["salt", "olive-oil", "rice-long-grain-white"]
    assert body["default_budget_cents"] == 4500


def test_put_still_takes_full_v3_settings(client):
    reply = client.put("/api/v1/settings", json=_with(household_size=2, onboarding_completed=True))
    assert reply.status_code == 200 and reply.json()["settings"]["household_size"] == 2
    assert client.put("/api/v1/settings", json=_with(schema_version=2)).status_code == 422


def test_preview_of_valid_settings_has_summary_lines_and_saves_nothing(client, seeded_db):
    changes = {"household_size": 2, "default_budget_cents": 4500, "always_have": ["salt", "black-pepper"]}
    reply = client.post("/api/v1/settings/preview", json=changes)
    assert reply.status_code == 200, reply.text
    preview = reply.json()
    assert preview["valid"] is True and preview["errors"] == []
    assert preview["kcal_planned_display"] == "1,800 of 1,800 kcal a day planned"
    lines = {line["key"]: line["value"] for line in preview["summary"]}
    assert list(lines) == [
        "people",
        "budget",
        "targets",
        "meals",
        "cook_days",
        "equipment",
        "stores",
        "food_rules",
        "always_have",
    ]
    assert lines["people"] == "2 people"
    assert lines["budget"] == "$45.00 (a starting point)"
    assert lines["targets"] == "1,800 kcal · 100 g protein"
    assert (
        lines["meals"]
        == "Breakfast 400 · Lunch 550 · Dinner 650 · Protein dessert 200 (1,800 of 1,800 kcal planned)"
    )
    assert lines["cook_days"] == "Mon, Wed, Thu, Sat, Sun · 45 min hands-on"
    assert lines["equipment"] == "Stovetop, Oven, Air fryer, Microwave"
    assert lines["stores"] == "1 Stop & Shop · 2 Price Rite"
    assert lines["food_rules"] == "Beef: never · Pork: up to 1 meal a week · 10 held, 0 allowed"
    assert lines["always_have"] == "salt, black pepper"
    assert preview["settings"]["household_size"] == 2
    assert load_settings(seeded_db, current_user(seeded_db).id).household_size == 1  # not saved


def test_preview_of_invalid_settings_has_field_errors_and_still_the_planned_line(client):
    allocations = [{"slot": "lunch", "kcal": 1000}, {"slot": "dinner", "kcal": 900}]
    preview = client.post("/api/v1/settings/preview", json={"slot_allocations": allocations}).json()
    assert preview["valid"] is False and preview["summary"] == [] and preview["settings"] is None
    assert any("exceed the daily kcal target" in e["msg"] for e in preview["errors"])
    assert preview["kcal_planned_display"] == "1,900 of 1,800 kcal a day planned"
    preview = client.post("/api/v1/settings/preview", json={"store_order": ["Nowhere"]}).json()
    assert preview["valid"] is False and preview["errors"][0]["loc"] == ["store_order"]
    preview = client.post("/api/v1/settings/preview", json={"daily_kcal_target": "lots"}).json()
    assert preview["errors"][0]["loc"] == ["daily_kcal_target"] and preview["kcal_planned_display"] is None


def test_summary_lines_follow_the_settings(seeded_db):
    user = current_user(seeded_db)
    s = load_settings(seeded_db, user.id).model_copy(
        update={"daily_protein_target_g": 0, "frequency_caps": [], "always_have": []}
    )
    schedule = [
        d.model_copy(update={"cook_minutes": 30}) if d.weekday.value == "mon" else d for d in s.cook_schedule
    ]
    s = s.model_copy(update={"cook_schedule": schedule})
    lines = {line.key: line.value for line in service.settings_summary(seeded_db, user.id, s)}
    assert lines["people"] == "1 person" and lines["budget"] == "No limit"
    assert lines["targets"] == "1,800 kcal · no protein target"
    assert lines["cook_days"] == "Mon 30 min, Wed 45 min, Thu 45 min, Sat 45 min, Sun 45 min"
    assert lines["food_rules"].startswith("Beef: never · ") and "Pork" not in lines["food_rules"]
    assert lines["always_have"] == "Nothing yet"


def test_always_have_options_list_common_staples_first(client):
    """S2 (step 2b.2): every ingredient that can be Always have, common staples first, your choices marked."""
    client.patch("/api/v1/settings", json={"always_have": ["garlic", "cumin-ground"]})
    reply = client.get("/api/v1/settings/always-have")
    assert reply.status_code == 200, reply.text
    options = reply.json()
    slugs = [o["slug"] for o in options]
    assert slugs[:7] == [
        "salt",
        "black-pepper",
        "olive-oil",
        "vegetable-oil",
        "rice-long-grain-white",
        "garlic",
        "onion-yellow",
    ]
    common = [o for o in options if o["common"]]
    assert options[: len(common)] == common  # the common ones come first, then the rest by name
    assert "cumin-ground" in {o["slug"] for o in common}  # assume-in-stock spices count as common
    rest = [o["name"] for o in options[len(common) :]]
    assert rest == sorted(rest)
    assert {o["slug"] for o in options if o["selected"]} == {"garlic", "cumin-ground"}
    assert "water" not in slugs  # always Always have, never listed
    assert "beef-broth" not in slugs and "beef-tallow" not in slugs  # beef can't be Always have


def test_stores_list_your_grocery_stores_in_order(client):
    stores = client.get("/api/v1/stores").json()
    assert [(s["name"], s["order"]) for s in stores] == [("Stop & Shop", 1), ("Price Rite", 2)]  # no "Other"


def test_adding_a_store_by_name_is_idempotent(client, seeded_db):
    reply = client.post("/api/v1/stores", json={"name": "  Market   Basket "})
    assert reply.status_code == 201, reply.text
    store = reply.json()
    assert store["name"] == "Market Basket" and store["order"] is None and store["priority"] == 4
    again = client.post("/api/v1/stores", json={"name": "market basket"})
    assert again.status_code == 200 and again.json()["id"] == store["id"]
    assert [s["name"] for s in client.get("/api/v1/stores").json()][-1] == "Market Basket"
    reply = client.patch("/api/v1/settings", json={"store_order": ["Stop & Shop", "Market Basket"]})
    assert reply.status_code == 200, reply.text
    stores = {s["name"]: s["order"] for s in client.get("/api/v1/stores").json()}
    assert stores == {"Stop & Shop": 1, "Market Basket": 2, "Price Rite": None}


def test_the_background_source_is_not_a_store_you_add(client):
    reply = client.post("/api/v1/stores", json={"name": "other"})
    assert reply.status_code == 422 and "items your stores don't carry" in reply.json()["detail"]
    assert client.post("/api/v1/stores", json={"name": ""}).status_code == 422
