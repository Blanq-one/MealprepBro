"""The quick-add amount picker (step 2b.1, AC 5): Full, ¾, ½ and ¼ are right for mass, count-pack and piece
items, and custom amounts in the item's units are converted on the server."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Ingredient, InventoryItem
from app.domain.amount_options import amount_options, custom_units, noun, option_quantity, plural
from app.domain.units import GRAMS_PER_UNIT, ML_PER_UNIT, IngredientUnits, UnitKind

LB = GRAMS_PER_UNIT["lb"]
MASS = IngredientUnits("chicken thigh", UnitKind.MASS)
EGGS = IngredientUnits("egg, large", UnitKind.COUNT, named_units={"large": Decimal(50)})


def displays(options):
    return [o.display for o in options]


def test_mass_options_are_exact_fractions_of_the_package():
    family_pack = 3 * LB
    options = amount_options(family_pack, "g", "chicken thigh")
    assert [o.key for o in options] == ["full", "three_quarters", "half", "quarter"]
    assert displays(options) == [
        "Full · 3 lb (1,361 g)",
        "¾ · 2.25 lb (1,021 g)",
        "½ · 1.5 lb (680 g)",
        "¼ · 12 oz (340 g)",
    ]
    assert [o.quantity for o in options] == [
        Decimal("1360.777"),
        Decimal("1020.583"),
        Decimal("680.389"),
        Decimal("340.194"),
    ]
    assert all(o.unit == "g" for o in options)
    assert displays(amount_options(family_pack, "g", "chicken thigh", us=False))[2] == "½ · 680 g"


def test_volume_options():
    half_gallon = 64 * ML_PER_UNIT["fl_oz"]
    assert displays(amount_options(half_gallon, "ml", "milk")) == [
        "Full · 8 cups (1,893 ml)",
        "¾ · 6 cups (1,420 ml)",
        "½ · 4 cups (946 ml)",
        "¼ · 2 cups (473 ml)",
    ]
    assert amount_options(ML_PER_UNIT["cup"] * 4, "ml", "x")[3].display == "¼ · 1 cup (237 ml)"
    assert amount_options(Decimal(170), "ml", "x")[3].display == "¼ · 2.9 tbsp (43 ml)"


def test_a_pack_of_pieces_rounds_to_whole_pieces():
    assert displays(amount_options(Decimal(12), "count", "egg")) == [
        "Full · 12 eggs",
        "¾ · 9 eggs",
        "½ · 6 eggs",
        "¼ · 3 eggs",
    ]
    assert [o.quantity for o in amount_options(Decimal(30), "count", "tortilla")] == [30, 23, 15, 8]
    # a 2-pack: ¾ would be 2 again and ¼ would be 1 again, so they're left out
    assert [(o.key, o.quantity) for o in amount_options(Decimal(2), "count", "avocado")] == [
        ("full", 2),
        ("half", 1),
    ]


def test_one_piece_is_split_into_fractions():
    cabbage = noun("cabbage, green", {"head": Decimal(908), "cup_shredded": Decimal(70)})
    assert cabbage == "head"
    assert displays(amount_options(Decimal(1), "count", cabbage)) == ["1 head", "¾ head", "½ head", "¼ head"]
    assert option_quantity("quarter", Decimal(1), "count") == Decimal("0.25")
    assert displays(amount_options(Decimal(1), "count", noun("bell pepper")))[2] == "½ bell pepper"


def test_piece_names_and_plurals():
    assert noun("egg, large", {"large": Decimal(50)}) == "egg"
    assert noun("flour tortilla (Price Rite, 37 g)") == "flour tortilla"
    assert [plural(w) for w in ("egg", "tomato", "peach", "berry", "head", "loaf")] == [
        "eggs",
        "tomatoes",
        "peaches",
        "berries",
        "heads",
        "loaves",
    ]


def test_custom_units_start_from_the_full_amount_in_natural_units_first():
    units = custom_units(3 * LB, "g", MASS, "chicken thigh")
    assert [(u.unit, u.label, u.step, u.start) for u in units] == [
        ("lb", "lb", Decimal("0.25"), Decimal("3.00")),
        ("oz", "oz", Decimal(1), Decimal(48)),
        ("g", "g", Decimal(25), Decimal(1350)),
    ]
    eggs = custom_units(Decimal(12), "count", EGGS, "egg")
    assert [(u.unit, u.label, u.step, u.start) for u in eggs] == [("count", "eggs", Decimal(1), Decimal(12))]
    tomatoes = IngredientUnits("tomato", UnitKind.COUNT, count_unit_weight_g=Decimal(123))
    loose = custom_units(Decimal(1), "count", tomatoes, "tomato")
    assert [(u.unit, u.step) for u in loose] == [
        ("count", Decimal("0.5")),
        ("lb", Decimal("0.25")),
        ("oz", 1),
        ("g", 25),
    ]
    assert [
        u.unit for u in custom_units(Decimal(500), "ml", IngredientUnits("oil", UnitKind.VOLUME), "oil")
    ] == [
        "cup",
        "fl_oz",
        "ml",
    ]


# ---------------- through the API ----------------
def ingredient_id(session, slug):
    return session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()


def picks(client):
    return {p["name"]: p for p in client.get("/api/v1/inventory/quick-picks").json()}


def test_quick_picks_carry_amount_options_and_custom_units(client):
    by_name = picks(client)
    chicken = by_name["chicken thigh, boneless skinless"]
    assert chicken["amount_options"][0]["key"] == "full"  # the default
    assert chicken["amount_options"][2]["display"] == "½ · 1.5 lb (680 g)"
    assert [u["unit"] for u in chicken["custom_units"]] == ["lb", "oz", "g"]
    eggs = by_name["egg, large"]
    assert [o["display"] for o in eggs["amount_options"]][2] == "½ · 6 eggs"
    assert eggs["custom_units"][0]["label"] == "eggs"
    tomato = by_name["tomato"]  # sold loose: one piece
    assert [o["display"] for o in tomato["amount_options"]] == [
        "1 tomato",
        "¾ tomato",
        "½ tomato",
        "¼ tomato",
    ]


def bulk(client, **item):
    return client.post("/api/v1/inventory/bulk", json={"items": [{"location": "fridge", **item}]})


def lot(session, lot_id):
    return session.get(InventoryItem, lot_id)


def test_bulk_add_by_option_key_stores_that_share_of_the_usual_package(client, seeded_db):
    chicken = ingredient_id(seeded_db, "chicken-thigh-boneless-skinless")
    reply = bulk(client, ingredient_id=chicken, amount_option="half")
    assert reply.status_code == 201, reply.text
    added = lot(seeded_db, reply.json()[0]["id"])
    assert (added.quantity, added.unit) == (Decimal("680.389"), "g")
    eggs = ingredient_id(seeded_db, "egg-large")
    added = lot(seeded_db, bulk(client, ingredient_id=eggs, amount_option="quarter").json()[0]["id"])
    assert (added.quantity, added.unit) == (Decimal(3), "count")


def test_bulk_add_converts_a_custom_amount_on_the_server(client, seeded_db):
    chicken = ingredient_id(seeded_db, "chicken-thigh-boneless-skinless")
    reply = bulk(client, ingredient_id=chicken, custom_amount="1.25", custom_unit="lb")
    assert reply.status_code == 201, reply.text
    added = lot(seeded_db, reply.json()[0]["id"])
    assert (added.quantity, added.unit) == (Decimal("566.990"), "g")
    tomato = ingredient_id(seeded_db, "tomato")
    added = lot(
        seeded_db,
        bulk(client, ingredient_id=tomato, custom_amount="1.5", custom_unit="count").json()[0]["id"],
    )
    assert (added.quantity, added.unit) == (Decimal("1.5"), "count")


@pytest.mark.parametrize(
    ("item", "message"),
    [
        ({"custom_amount": "2", "custom_unit": "count"}, "can be added in lb, oz, g"),
        ({"custom_amount": "2", "custom_unit": "furlong"}, "unknown unit"),
    ],
)
def test_custom_units_the_item_doesnt_offer_are_refused(client, seeded_db, item, message):
    chicken = ingredient_id(seeded_db, "chicken-thigh-boneless-skinless")
    reply = bulk(client, ingredient_id=chicken, **item)
    assert reply.status_code == 422 and message in reply.json()["detail"]


def test_an_amount_comes_one_way_only(client, seeded_db):
    chicken = ingredient_id(seeded_db, "chicken-thigh-boneless-skinless")
    reply = bulk(client, ingredient_id=chicken, amount_option="half", quantity="2", unit="lb")
    assert reply.status_code == 422
    assert bulk(client, ingredient_id=chicken).status_code == 422
    assert bulk(client, ingredient_id=chicken, custom_amount="2").status_code == 422
    assert bulk(client, ingredient_id=chicken, quantity="2", unit="lb").status_code == 201  # as before


def test_an_option_needs_a_usual_amount(client, seeded_db):
    ginger = ingredient_id(seeded_db, "ginger")  # sold loose by weight: no package, not a count item
    reply = bulk(client, ingredient_id=ginger, amount_option="full")
    assert reply.status_code == 422 and "no usual package size" in reply.json()["detail"]
