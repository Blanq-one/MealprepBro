"""CLI commands against the seeded test database (read-only commands only; seeding is covered elsewhere)."""

import io
import json

import pytest

from app import cli
from app.auth.passwords import verify_password
from app.deploy import should_migrate


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


def test_plan_week_prints_the_week_from_seeds_with_zero_llm_calls(use_test_db, capsys):
    assert cli.main(["plan-week", "--week", "2026-10-12", "--no-llm", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Week of Mon Oct 12, 2026" in out and "0 LLM calls, 0 tokens" in out
    assert "TUE Oct 13 | leftovers, no cooking" in out and "FRI Oct 16 | leftovers, no cooking" in out
    assert out.count("  Day ") == 7 and "  WEEK " in out
    assert "Regular groceries by store" in out and "Stop & Shop" in out and "Price Rite" in out
    assert "Also buy this week (stock-up, lasts beyond this week)" in out and "protein powder" in out
    assert "regular +" in out and "stock-up" in out
    assert "Mode:      shop: your inventory first, then the grocery list (no budget" in out
    assert "| target 100 g/day, week >= 700 g (a floor; more earns nothing)" in out
    assert "Cash this trip" in out and "Food eaten" in out and "Expected waste" in out
    assert "start to finish" in out
    assert "Freeze on shopping day" in out
    assert "(dry run: nothing was saved)" in out


def test_plan_week_explains_an_infeasible_week(use_test_db, capsys):
    args = ["--slot", "dinner=550", "--slot", "drink=100"]  # no drink recipe, and generation is off
    code = cli.main(["plan-week", "--week", "2026-10-12", "--no-llm", "--dry-run", *args])
    assert code == 1
    out = capsys.readouterr().out
    assert "INFEASIBLE" in out and "No plan fits this week" in out
    assert "No drink recipes are available" in out


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--mode", "inventory", "--budget", "50"], "--budget is for shop mode"),
        (["--topup", "10"], "--topup is for inventory mode"),
    ],
)
def test_plan_week_rejects_a_limit_for_the_other_mode(use_test_db, capsys, args, message):
    assert cli.main(["plan-week", "--week", "2026-10-12", "--no-llm", "--dry-run", *args]) == 2
    assert message in capsys.readouterr().err


def test_hash_password_prints_a_hash_and_a_fresh_session_secret(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("my kitchen password\n"))
    assert cli.main(["hash-password", "--stdin"]) == 0
    lines = dict(line.split("=", 1) for line in capsys.readouterr().out.strip().splitlines())
    assert verify_password("my kitchen password", lines["AUTH_PASSWORD_HASH"])
    assert len(lines["SESSION_SECRET"]) >= 48 and "$" not in lines["AUTH_PASSWORD_HASH"]
    monkeypatch.setattr("sys.stdin", io.StringIO("short\n"))
    assert cli.main(["hash-password", "--stdin"]) == 2


def test_openapi_writes_the_schema_the_pwa_uses(tmp_path):
    out = tmp_path / "openapi.json"
    assert cli.main(["openapi", "--out", str(out)]) == 0
    spec = json.loads(out.read_text(encoding="utf-8"))
    assert "/api/v1/plans" in spec["paths"] and "/api/v1/auth/login" in spec["paths"]


def test_the_vercel_build_migrates_production_only_when_asked():
    prod = {
        "VERCEL_ENV": "production",
        "DATABASE_URL_UNPOOLED": "postgres://x",
        "RUN_MIGRATIONS_ON_DEPLOY": "1",
    }
    assert should_migrate(prod)[0]
    assert not should_migrate({**prod, "VERCEL_ENV": "preview"})[0]
    assert not should_migrate({**prod, "RUN_MIGRATIONS_ON_DEPLOY": "0"})[0]
    assert not should_migrate({"VERCEL_ENV": "production", "RUN_MIGRATIONS_ON_DEPLOY": "1"})[0]
