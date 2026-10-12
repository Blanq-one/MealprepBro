"""Storage per prep item and stop state (step 2b.10, FLOW_SPEC §19.4, AC 1 and 2): a test per row of the
table, the strictest line, partly cooked protein never stored (V2), fresh items made on the day (V1), the
freezer rules, and the FoodKeeper rows checked against the saved FoodKeeper file."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.domain.enums import PrepState
from app.domain.foodkeeper import FOODKEEPER_DATA_VERSION, FOODKEEPER_FILE, FOODKEEPER_ROWS
from app.domain.prep_storage import StorageLine, prep_storage

REPO = Path(__file__).resolve().parents[4]


def line(slug, category=None, tags=(), role="protein", preparation=None):
    return StorageLine(slug, category, frozenset(tags), role, preparation)


SALT = line("salt", role="seasoning")
OIL = line("olive-oil", role="fat")
CHICKEN = line("chicken-thigh-boneless-skinless", "poultry", {"poultry"})
GROUND_TURKEY = line("ground-turkey-93", "poultry", {"poultry"})
SALMON = line("salmon", "fish_shellfish", {"fish"})
SHRIMP = line("shrimp", "fish_shellfish", {"shellfish"})
PORK_CHOP = line("pork-chop-boneless", "whole_cut_meat", {"pork"})
EGG = line("egg-large", "egg", {"egg"})
RICE = line("rice-long-grain-white", role="carb")
QUINOA = line("quinoa", role="carb")
PASTA = line("pasta-dry", role="carb")
WATER = line("water", role="other")
LENTILS = line("lentils-red", tags=(), role="protein")
POTATO = line("potato-russet", role="carb")
CARROT = line("carrot", role="vegetable")
YOGURT = line("greek-yogurt-nonfat", tags={"dairy"}, role="sauce")
CUCUMBER = line("cucumber", role="vegetable")
ROMAINE = line("romaine", role="vegetable")
BROTH = line("chicken-broth-low-sodium", tags={"poultry"}, role="other")
TUNA = line("tuna-canned", tags={"fish"})


def storage(lines, state, *, freezes_well=True, days=3):
    return prep_storage(lines, state, freezes_well=freezes_well, leftover_fridge_days=days)


# ---- raw or marinated: the raw rows, short end; freezes the same day ----
@pytest.mark.parametrize(
    ("protein", "days", "row"),
    [
        (CHICKEN, 1, "Fresh poultry, chicken or turkey, pieces"),
        (GROUND_TURKEY, 1, "Hamburger, ground meats and ground poultry"),
        (SALMON, 1, "Fin fish"),
        (SHRIMP, 3, "Shellfish, shrimp, crayfish"),
        (PORK_CHOP, 3, "Fresh beef, veal, lamb, and pork, chops"),
    ],
    ids=["poultry pieces", "ground meat or poultry", "fin fish", "shrimp", "pork chops"],
)
@pytest.mark.parametrize("state", [PrepState.RAW, PrepState.MARINATED])
def test_raw_or_marinated_protein_keeps_the_short_end_of_its_row_and_freezes(protein, days, row, state):
    s = storage([protein, YOGURT, SALT, OIL], state, freezes_well=False)
    assert s.stored and not s.made_on_the_day
    assert s.fridge_days == days
    assert s.freezer  # raw or marinated meat, poultry or fish always freezes, whatever the item's flag
    assert s.sources[0].food.startswith(row)
    assert "freeze it the same day" in s.note
    assert s.fridge_until(date(2026, 10, 11)) == date(2026, 10, 11 + days)


def test_raw_eggs_in_a_mixture_keep_like_raw_whites_and_yolks():
    s = storage([EGG, SALT], PrepState.RAW)
    assert (s.fridge_days, s.freezer) == (2, True)
    assert s.sources[0].food == "Eggs, raw egg whites and yolks"


# ---- partly cooked (V2) ----
@pytest.mark.parametrize("protein", [CHICKEN, GROUND_TURKEY, SALMON, SHRIMP, PORK_CHOP, EGG])
def test_partly_cooked_meat_poultry_fish_or_eggs_is_never_stored(protein):
    s = storage([protein, CARROT, SALT], PrepState.PARTLY_COOKED)
    assert not s.stored and not s.made_on_the_day
    assert s.fridge_days == 0 and not s.freezer
    assert "isn't stored" in s.note


def test_partly_cooked_vegetables_keep_like_cooked_vegetables():
    s = storage([POTATO, SALT, OIL], PrepState.PARTLY_COOKED)
    assert s.stored and s.fridge_days == 3 and s.freezer
    assert s.sources[0].citation.startswith("USDA FoodKeeper") and "without meat" in s.sources[0].food


# ---- cooked ----
def test_cooked_meat_or_poultry_keeps_your_leftover_days():
    s = storage([CHICKEN, CARROT, SALT], PrepState.COOKED)
    assert (s.fridge_days, s.freezer) == (3, True)
    assert s.sources[0].food == "Leftovers, cooked meat or poultry"
    assert storage([CHICKEN], PrepState.COOKED, days=4).fridge_days == 4  # your setting, up to 4


def test_cooked_food_freezes_only_if_it_freezes_well():
    assert not storage([CHICKEN, SALT], PrepState.COOKED, freezes_well=False).freezer


def test_a_cooked_egg_dish_keeps_like_a_casserole_with_eggs():
    s = storage([EGG, CARROT, SALT], PrepState.COOKED)
    assert (s.fridge_days, s.freezer) == (3, True)
    assert s.sources[0].food == "Eggs, casseroles with eggs"


def test_only_hard_cooked_eggs_keep_a_week_and_never_freeze():
    s = storage([line("egg-large", "egg", {"egg"}, preparation="hard-boiled"), SALT], PrepState.COOKED)
    assert (s.fridge_days, s.freezer) == (7, False)
    assert s.sources[0].food == "Eggs, hard-cooked eggs"
    # with anything else in it, it's an egg dish
    assert (
        storage(
            [line("egg-large", "egg", {"egg"}, preparation="hard-boiled"), CARROT], PrepState.COOKED
        ).fridge_days
        == 3
    )


@pytest.mark.parametrize(
    ("protein", "row"),
    [(SALMON, "Cooked fish, all"), (SHRIMP, "Cooked shellfish, all"), (TUNA, "Cooked fish, all")],
)
def test_cooked_fish_and_shellfish_use_foodkeeper(protein, row):
    s = storage([protein, RICE, SALT], PrepState.COOKED)
    assert s.fridge_days == 3
    assert s.sources[0].food == row and s.sources[0].citation.startswith("USDA FoodKeeper")


@pytest.mark.parametrize(
    ("lines", "grain_row"),
    [
        ([RICE, WATER, SALT], "Cooked rice"),
        ([QUINOA, WATER], "Quinoa, cooked"),
        ([PASTA, WATER, OIL], "Cooked pasta"),
        ([RICE, CARROT, OIL], None),  # not only the grain
        ([POTATO, CARROT, OIL, SALT], None),  # cooked vegetables
        ([LENTILS, line("tomato", role="vegetable"), WATER], None),  # dal
    ],
    ids=["rice", "quinoa", "pasta", "vegetable rice", "roasted vegetables", "dal"],
)
def test_cooked_food_without_meat_fish_or_eggs_uses_foodkeeper_leftovers(lines, grain_row):
    s = storage(lines, PrepState.COOKED)
    assert (s.fridge_days, s.freezer) == (3, True)  # your 3 days, every row's upper end at least 4
    foods = [src.food for src in s.sources]
    assert foods[0].startswith("Leftovers, without meat, fish, poultry, or egg")
    assert foods[1:] == ([grain_row] if grain_row else [])
    assert storage(lines, PrepState.COOKED, days=4).fridge_days == 4


def test_a_broth_doesnt_make_rice_poultry():
    s = storage([RICE, BROTH], PrepState.COOKED)
    assert s.sources[0].food.startswith("Leftovers, without meat")


# ---- raw, ready to eat: no row (V1) ----
@pytest.mark.parametrize(
    "lines",
    [[CUCUMBER, ROMAINE, OIL], [YOGURT, CUCUMBER, SALT], [YOGURT, line("lemon-juice", role="sauce")]],
    ids=["cut vegetables or a salad", "raita", "a yogurt sauce"],
)
def test_raw_food_without_meat_fish_or_eggs_is_made_on_the_eating_day(lines):
    s = storage(lines, PrepState.RAW)
    assert s.made_on_the_day and not s.stored
    assert s.fridge_days == 0 and not s.freezer and s.sources == ()
    assert "Made fresh on the day you eat it (5 min)" in s.note


def test_a_raw_item_whose_protein_has_no_raw_row_is_made_on_the_day():
    s = storage([TUNA, line("chickpeas-canned", role="protein"), CUCUMBER], PrepState.RAW)
    assert s.made_on_the_day


# ---- the strictest line wins ----
def test_the_strictest_line_wins():
    raw = storage([SHRIMP, CHICKEN, SALT], PrepState.MARINATED)  # shrimp 3 days, chicken 1
    assert raw.fridge_days == 1 and len(raw.sources) == 2
    cooked = storage([line("egg-large", "egg", {"egg"}, preparation="hard-boiled"), SHRIMP], PrepState.COOKED)
    assert cooked.fridge_days == 3  # not the hard-cooked eggs' week


def test_hard_cooked_eggs_and_their_rows_never_freeze_even_if_flagged():
    s = storage(
        [line("egg-large", "egg", {"egg"}, preparation="hard-cooked")], PrepState.COOKED, freezes_well=True
    )
    assert not s.freezer


# ---- the FoodKeeper transcription ----
def _foodkeeper_products() -> dict[int, dict[str, Any]]:
    data = json.loads((REPO / FOODKEEPER_FILE).read_text(encoding="utf-8"))
    sheets = {sheet["name"]: sheet["data"] for sheet in data["sheets"]}
    out = {}
    for cells in sheets["Product"]:
        row = {k: v for cell in cells for k, v in cell.items()}
        out[int(row["ID"])] = row
    version = [{k: v for c in cells for k, v in c.items()} for cells in sheets["Version"]]
    assert any(
        v["Data_Version_Number"] == FOODKEEPER_DATA_VERSION and v["Current_Version"] == "Yes" for v in version
    )
    return out


def _span(row: dict[str, Any], prefix: str) -> str:
    low, high, metric = row[f"{prefix}_Min"], row[f"{prefix}_Max"], row[f"{prefix}_Metric"].lower()
    low, high = int(low), int(high)
    return f"{low} {metric}" if low == high else f"{low} to {high} {metric}"


@pytest.mark.parametrize("row", FOODKEEPER_ROWS, ids=[r.key for r in FOODKEEPER_ROWS])
def test_each_foodkeeper_row_matches_the_saved_file(row):
    """The backend image is built from backend/ alone, so docs/sources isn't there and this is skipped (as the
    pantry catalog's review sheet check); it runs in the repo."""
    if not (REPO / FOODKEEPER_FILE).is_file():
        pytest.skip("docs/sources isn't part of the backend image")
    product = _foodkeeper_products()[row.product_id]
    assert product["Name"] == row.name
    assert product.get("Name_subtitle") == row.subtitle
    assert _span(product, "Refrigerate") == row.refrigerator
    freezer = (
        _span(product, "Freeze")
        if product.get("Freeze_Min") is not None
        else (_span(product, "DOP_Freeze") + " from the date of purchase")
    )
    assert freezer == row.freezer
