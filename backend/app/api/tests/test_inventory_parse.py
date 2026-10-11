"""Natural-language quick add (Phase 2): the LLM reads the note, code resolves and converts, and nothing is
saved until you confirm with POST /inventory/bulk."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.api.deps import get_llm_client_factory
from app.db.models import GenerationRun, Ingredient, InventoryEvent, InventoryItem, LlmCall
from app.llm.fake import FakeLLMClient, response
from app.services.inventory_parse import is_written, numbers_written

NOTE = "2 lb chicken thighs and half a cabbage"


def item(text, name, quantity, unit, location=None):
    return {"text": text, "name": name, "quantity": quantity, "unit": unit, "location": location}


@pytest.fixture
def use_llm(client):
    def install(*replies) -> FakeLLMClient:
        fake = FakeLLMClient([response(r) for r in replies])
        client.app.dependency_overrides[get_llm_client_factory] = lambda: lambda: fake
        return fake

    return install


def parse(client, text=NOTE):
    return client.post("/api/v1/inventory/parse", json={"text": text})


def lots(session):
    return session.scalar(select(func.count()).select_from(InventoryItem))


def ingredient_id(session, slug):
    return session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()


def test_amounts_are_converted_by_code_and_nothing_is_saved(client, use_llm, seeded_db):
    use_llm(
        {
            "items": [
                item("2 lb chicken thighs", "chicken thighs", 2, "lb"),
                item("half a cabbage", "cabbage", 0.5, "count"),
            ]
        }
    )
    before = lots(seeded_db)
    reply = parse(client)
    assert reply.status_code == 200, reply.text
    chicken, cabbage = reply.json()["items"]
    assert chicken["status"] == "ok" and chicken["ingredient_name"] == "chicken thigh, boneless skinless"
    assert Decimal(chicken["quantity"]) == Decimal("907.185") and chicken["unit"] == "g"  # 2 × 453.59237
    assert chicken["display"] == "907 g (2.00 lb)" and chicken["location"] == "fridge"
    assert cabbage["status"] == "ok" and Decimal(cabbage["quantity"]) == Decimal("0.5")
    assert cabbage["unit"] == "count"
    assert lots(seeded_db) == before  # a preview only
    run = seeded_db.get(GenerationRun, reply.json()["run_id"])
    assert run.purpose == "inventory_parse" and run.status == "succeeded"
    calls = seeded_db.scalars(select(LlmCall).where(LlmCall.generation_run_id == run.id)).all()
    assert [c.purpose for c in calls] == ["inventory_parse"]


def test_confirming_the_preview_saves_the_lots(client, use_llm, seeded_db):
    use_llm({"items": [item("2 lb chicken thighs", "chicken thighs", 2, "lb")]})
    chicken = parse(client).json()["items"][0]
    saved = client.post(
        "/api/v1/inventory/bulk",
        json={
            "source": "parse",
            "items": [
                {
                    "ingredient_id": chicken["ingredient_id"],
                    "quantity": chicken["quantity"],
                    "unit": chicken["unit"],
                    "location": chicken["location"],
                }
            ],
        },
    )
    assert saved.status_code == 201 and saved.json()[0]["display"] == "907 g (2.00 lb)"
    event = seeded_db.scalars(select(InventoryEvent).where(InventoryEvent.reason == "parse_add")).one()
    assert event.delta_quantity == Decimal("907.185")


def test_invalid_llm_output_is_retried_with_the_error(client, use_llm):
    fake = use_llm(
        "Sure! Here are your items: chicken", {"items": [item("half a cabbage", "cabbage", 0.5, "count")]}
    )
    reply = parse(client, "half a cabbage")
    assert reply.status_code == 200 and fake.calls == 2
    assert "not valid JSON" in fake.requests[1].messages[-1]["content"]


def test_a_quantity_the_note_never_states_needs_confirmation(client, use_llm):
    use_llm({"items": [item("some chicken thighs", "chicken thighs", 2, "lb")]})
    result = parse(client, "some chicken thighs").json()["items"][0]
    assert result["status"] == "needs_confirmation" and "doesn't say 2" in result["message"]
    assert Decimal(result["quantity"]) == Decimal("907.185")  # shown so you can check it, not saved


def test_unknown_names_come_back_unresolved_with_suggestions(client, use_llm):
    use_llm(
        {"items": [item("2 dragonfruit", "dragonfruit", 2, "count"), item("eggz", "chicken thighz", 1, "lb")]}
    )
    unknown, typo = parse(client, "2 dragonfruit, 1 lb chicken thighz").json()["items"]
    assert unknown["status"] == "unresolved" and unknown["ingredient_id"] is None
    assert typo["status"] in ("ok", "unresolved")
    if typo["status"] == "unresolved":
        assert any("chicken thigh" in s["name"] for s in typo["suggestions"])


def test_beef_is_flagged_and_can_never_be_saved(client, use_llm, seeded_db):
    use_llm({"items": [item("1 lb ground beef", "ground beef", 1, "lb")]})
    beef = parse(client, "1 lb ground beef").json()["items"][0]
    assert beef["status"] == "excluded" and "beef" in beef["message"]
    refused = client.post(
        "/api/v1/inventory/bulk",
        json={
            "items": [
                {
                    "ingredient_id": ingredient_id(seeded_db, "ground-beef-85"),
                    "quantity": "454",
                    "unit": "g",
                    "location": "fridge",
                }
            ]
        },
    )
    assert refused.status_code == 422 and "excluded" in refused.json()["detail"]


def test_a_pack_of_bacon_is_fine_in_inventory(client, use_llm, seeded_db):
    use_llm({"items": [item("a pack of bacon", "bacon", 1, "package")]})
    bacon = parse(client, "a pack of bacon").json()["items"][0]
    # pork is allowed (its cap applies to meals); with no usual package size you enter the amount
    assert bacon["status"] == "needs_confirmation" and bacon["ingredient_name"] == "bacon"
    saved = client.post(
        "/api/v1/inventory/bulk",
        json={
            "items": [
                {
                    "ingredient_id": bacon["ingredient_id"],
                    "quantity": "12",
                    "unit": "oz",
                    "location": "fridge",
                }
            ]
        },
    )
    assert saved.status_code == 201 and saved.json()[0]["display"].startswith("340 g")


def test_a_package_uses_the_usual_product_size(client, use_llm):
    use_llm({"items": [item("a carton of eggs", "eggs", 1, "package")]})
    eggs = parse(client, "a carton of eggs").json()["items"][0]
    assert eggs["status"] == "ok" and Decimal(eggs["quantity"]) == 12 and eggs["product_id"]


def test_an_llm_that_stays_invalid_is_a_502_and_saves_nothing(client, use_llm, seeded_db):
    use_llm("nope", "still nope", "nope again")
    before = lots(seeded_db)
    reply = parse(client, "2 lb chicken thighs")
    assert reply.status_code == 502 and reply.json()["title"] == "Couldn't read that note"
    assert lots(seeded_db) == before


def test_quick_picks_offer_usual_packages_and_skip_staples_and_beef(client):
    picks = client.get("/api/v1/inventory/quick-picks").json()
    names = {p["name"] for p in picks}
    assert picks and "salt" not in names and not any("beef" in n for n in names)
    eggs = next(p for p in picks if p["name"] == "egg, large")  # (egg whites are a pick of their own)
    assert eggs["product_id"] and Decimal(eggs["quantity"]) == 12


@pytest.mark.parametrize(
    ("note", "quantity", "written"),
    [
        ("2 lb chicken", 2, True),
        ("1.5 lb chicken", 1.5, True),
        ("1 1/2 cups rice", 1.5, True),
        ("½ cabbage", 0.5, True),
        ("half a cabbage", 0.5, True),
        ("a dozen eggs", 12, True),
        ("an onion", 1, True),
        ("some chicken", 2, False),
        ("2 lb chicken", 3, False),
    ],
)
def test_numeric_fidelity(note, quantity, written):
    assert is_written(quantity, note) is written


def test_numbers_written_reads_fractions_and_words():
    assert numbers_written("1 1/2 cups, ¼ tsp and two eggs") >= {Decimal("1.5"), Decimal("0.25"), Decimal(2)}
