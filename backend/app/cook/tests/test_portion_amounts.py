"""Step 2b.4 approval, A1: every recipe line says what one portion takes and, for a batch, the batch total
("1 scoop per portion · 4 scoops for the batch of 4"); a powder measured by the scoop always shows scoops."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.cook.tests.conftest import add_recipe, add_stock, ingredient_id
from app.cook.your_terms import PantryLot, note
from app.db.models import RecipeVersion
from app.domain.quantities import per_portion_amount, portion_note
from app.services.ingredient_data import load_by_slug

POWDER = "protein-powder-double-chocolate"


def page(api: Any, version_id: int, portions: int) -> dict[str, Any]:
    reply = api.get(f"/api/v1/recipe-versions/{version_id}", params={"portions": portions})
    assert reply.status_code == 200, reply.text
    body: dict[str, Any] = reply.json()
    return body


def line(body: dict[str, Any], ingredient: int) -> dict[str, Any]:
    return next(ln for ln in body["lines"] if ln["ingredient_id"] == ingredient)


def test_portion_notes_round_to_something_you_can_measure():
    assert portion_note(Decimal(4), "scoop", 4) == "1 scoop per portion · 4 scoops for the batch of 4"
    assert portion_note(Decimal("1.25"), "tsp", 4) == "⅜ tsp per portion · 1¼ tsp for the batch of 4"
    assert portion_note(Decimal(8), "count", 4) == "2 per portion · 8 for the batch of 4"
    assert portion_note(Decimal(680), "g", 4) == "170 g per portion · 680 g for the batch of 4"
    assert portion_note(Decimal(2), "scoop", 1) is None  # one portion: nothing to split
    assert per_portion_amount(Decimal("0.25"), "tsp", 4) == Decimal("0.125")  # never less than an eighth


def test_the_pudding_shows_scoops_per_portion_and_for_the_batch(api, seeded_db):
    pudding = seeded_db.scalars(
        select(RecipeVersion.id).where(RecipeVersion.title == "Double chocolate protein pudding")
    ).one()
    powder = ingredient_id(seeded_db, POWDER)
    four = line(page(api, pudding, 4), powder)
    assert four["amount_display"] == "4 scoops"
    assert four["portion_note"] == "1 scoop per portion · 4 scoops for the batch of 4"
    one = line(page(api, pudding, 1), powder)
    assert one["amount_display"] == "1 scoop" and one["portion_note"] is None


def test_a_powder_written_in_grams_still_shows_scoops(api, seeded_db):
    shake = add_recipe(
        seeded_db,
        "Chocolate shake",
        [(POWDER, 62, "g", "protein"), ("milk-2", 480, "ml", "dairy")],
        slots=("snack",),
        servings=2,
    )
    powder = line(page(api, shake.id, 2), ingredient_id(seeded_db, POWDER))
    assert powder["amount_display"] == "2 scoops"  # 62 g is two 31 g scoops
    assert powder["portion_note"] == "1 scoop per portion · 2 scoops for the batch of 2"


def test_pantry_and_your_terms_count_powder_in_scoops(api, seeded_db):
    add_stock(seeded_db, POWDER, 682)
    lots = api.get("/api/v1/inventory").json()
    tub = next(lot for lot in lots if lot["ingredient_id"] == ingredient_id(seeded_db, POWDER))
    assert tub["display"].startswith("22 scoops (")
    units = load_by_slug(seeded_db)[POWDER].units
    text = note(Decimal(62), "g", [PantryLot(1, Decimal(682), "g", "tub")], units)
    assert text == "uses 2 scoops, a little of your tub · 20 scoops left after"
