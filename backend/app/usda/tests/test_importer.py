import zipfile
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.db.models import UsdaFood, UsdaFoodNutrient, UsdaFoodPortion, UsdaNutrient
from app.seed.files import load_seed_files
from app.seed.loader import usda_nutrition_rows
from app.usda.importer import import_release
from app.usda.release import ReleaseError, find_releases, open_release
from app.usda.subset import build_subset

MINI = Path(__file__).parent / "fixtures" / "mini_release"
FAKE_IDS = (9900001, 9900002, 9900003, 9900004, 9900005)


def _counts(session):
    foods = session.scalar(select(func.count()).select_from(UsdaFood).where(UsdaFood.fdc_id.in_(FAKE_IDS)))
    values = session.scalar(
        select(func.count()).select_from(UsdaFoodNutrient).where(UsdaFoodNutrient.fdc_id.in_(FAKE_IDS))
    )
    portions = session.scalar(
        select(func.count()).select_from(UsdaFoodPortion).where(UsdaFoodPortion.fdc_id.in_(FAKE_IDS))
    )
    return foods, values, portions


def test_import_and_idempotent(db):
    report = import_release(db, MINI)
    assert report.release == "mini_release"
    assert report.foods == 3  # A, B, C; the sample_food row and malformed rows are skipped
    first = _counts(db)
    assert first == (3, 13, 2)
    again = import_release(db, MINI)
    assert again.foods == 3
    assert _counts(db) == first  # re-running leaves row counts unchanged


def test_malformed_rows_are_reported(db):
    report = import_release(db, MINI)
    assert report.skipped == {
        "malformed nutrient row": 1,
        "malformed food row": 2,
        "malformed food_nutrient row": 1,
        "duplicate food_nutrient row": 1,
        "unknown nutrient id": 1,
        "malformed food_portion row": 2,
    }
    assert any("line 15" in p for p in report.problems)  # the 'abc' amount


def test_food_fields(db):
    import_release(db, MINI)
    food = db.get(UsdaFood, 9900001)
    assert food is not None
    assert (food.data_type, food.food_category, food.source_release) == (
        "sr_legacy_food",
        "Dairy and Egg Products",
        "mini_release",
    )
    assert db.get(UsdaFood, 9900003) is None
    assert db.get(UsdaNutrient, 2048).nutrient_nbr == "958"


def test_portions(db):
    import_release(db, MINI)
    cup = db.get(UsdaFoodPortion, 990001)
    assert (cup.modifier, cup.measure_unit, cup.gram_weight) == ("cup", None, Decimal("120.000"))
    tbsp = db.get(UsdaFoodPortion, 990002)
    assert (tbsp.measure_unit, tbsp.amount, tbsp.gram_weight) == (
        "tablespoon",
        Decimal("2.000"),
        Decimal("30.000"),
    )


def test_energy_falls_back_to_958_then_atwater(db):
    import_release(db, MINI)
    nutrients = load_seed_files().nutrients.nutrients
    energy_id = next(n.id for n in nutrients if n.code == "energy_kcal")

    def energy(fdc_id):
        return next(
            (amount, source)
            for nid, amount, source, _ in usda_nutrition_rows(db, fdc_id, nutrients)
            if nid == energy_id
        )

    assert energy(9900001) == (Decimal("100.0000"), "usda")  # 208
    assert energy(9900002) == (Decimal("150.0000"), "usda")  # no 208 → 958 (not 957)
    assert energy(9900004) == (Decimal("170.0000"), "derived")  # P20 F10 C0 → 4/4/9


def test_reads_zip_downloads(tmp_path, db):
    zip_path = tmp_path / "FoodData_Central_mini_csv.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file in MINI.iterdir():
            zf.write(file, f"FoodData_Central_mini_csv/{file.name}")
    release = open_release(zip_path)
    assert release.name == "FoodData_Central_mini_csv"
    assert import_release(db, zip_path).foods == 3
    assert find_releases(tmp_path) == [zip_path]


def test_not_a_release(tmp_path):
    with pytest.raises(ReleaseError):
        open_release(tmp_path)
    bad_zip = tmp_path / "x.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("readme.txt", "nothing here")
    with pytest.raises(ReleaseError):
        open_release(bad_zip)


def test_subset_builder(tmp_path):
    out = build_subset(MINI, [9900002], [1003, 2048], tmp_path)
    release = open_release(out)
    assert [r["fdc_id"] for r in release.rows("food.csv")] == ["9900002"]
    assert {r["nutrient_id"] for r in release.rows("food_nutrient.csv")} == {"1003", "2048"}
    assert [r["id"] for r in release.rows("food_portion.csv")] == ["990002"]
    assert {r["id"] for r in release.rows("nutrient.csv")} == {"1003", "2048"}
