"""CLI commands against the seeded test database (read-only commands only; seeding is covered elsewhere)."""

import pytest

from app import cli


@pytest.fixture
def use_test_db(seeded, monkeypatch):
    monkeypatch.setattr(cli, "get_engine", lambda: seeded)


def test_safety_table_prints_values_and_citation(capsys):
    assert cli.main(["safety-table"]) == 0
    out = capsys.readouterr().out
    assert "poultry          165 F" in out
    assert "whole_cut_meat   145 F + 3-minute rest" in out
    assert "leftovers_reheat 165 F" in out
    assert "https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts" in out
    assert "pending" not in out
    assert "Cooked leftovers: 3 days in the fridge" in out
    assert "last reviewed September 19, 2023" in out
    assert "docs/sources/Cold Food Storage Chart _ FoodSafety.gov.pdf" in out
    assert "Chicken or turkey, pieces" in out and "9 months" in out


def test_ingredient_report_exits_zero_with_no_errors(use_test_db, capsys):
    assert cli.main(["ingredient-report"]) == 0
    out = capsys.readouterr().out
    assert "ERRORS (0)" in out
    assert "Held: excluded by default" in out
    assert "Pork meal components (frequency-capped)" in out


def test_usda_import_without_downloads_explains_what_to_do(tmp_path, monkeypatch, capsys):
    settings = cli.get_settings()
    monkeypatch.setattr(settings, "usda_raw_dir", tmp_path)
    assert cli.main(["usda-import"]) == 1
    assert "docs/data-sources.md" in capsys.readouterr().err


def test_unknown_command_is_rejected():
    with pytest.raises(SystemExit):
        cli.main(["nope"])
