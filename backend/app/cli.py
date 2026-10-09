"""Command line: `uv run python -m app.cli <command>`.

usda-import [PATH ...]   import USDA FoodData Central CSV zips (default: every zip in USDA_RAW_DIR)
usda-subset              rebuild the committed test fixture from the full zips
seed                     load seed data (idempotent; run after usda-import)
ingredient-report        data-quality report: errors, placeholders, held items, Atwater mismatches
safety-table             print the hardcoded food-safety table and its citation
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.db.session import get_engine
from app.domain import food_safety as fs
from app.seed.files import load_seed_files
from app.seed.loader import seed_all
from app.seed.report import build_report, format_report
from app.usda.importer import import_release
from app.usda.release import find_releases
from app.usda.subset import build_subset

SUBSET_DIR = BACKEND_DIR / "app" / "testing" / "fixtures" / "usda_subset"


def _usda_import(paths: Sequence[str]) -> int:

    targets = [Path(p) for p in paths] or find_releases(get_settings().usda_raw_dir)
    if not targets:
        print(
            f"No USDA releases found in {get_settings().usda_raw_dir}. See docs/data-sources.md.",
            file=sys.stderr,
        )
        return 1
    with Session(get_engine()) as session:
        for path in targets:
            report = import_release(session, path)
            print(
                f"{report.release}: {report.foods} foods, {report.nutrients} nutrients, "
                f"{report.food_nutrients} food-nutrient values, {report.portions} portions"
            )
            for reason, count in sorted(report.skipped.items()):
                print(f"  skipped {count}: {reason}")
        session.commit()
    return 0


def _usda_subset() -> int:

    files = load_seed_files()
    fdc_ids = {i.fdc_id for i in files.ingredients.ingredients if i.fdc_id is not None}
    nutrient_ids = {uid for n in files.nutrients.nutrients for uid in n.usda_nutrient_ids}
    for path in find_releases(get_settings().usda_raw_dir):
        out = build_subset(path, fdc_ids, nutrient_ids, SUBSET_DIR)
        print(f"wrote {out}")
    return 0


def _seed() -> int:

    with Session(get_engine()) as session:
        report = seed_all(session)
        session.commit()
    print(", ".join(f"{k}={v}" for k, v in report.counts.items()))
    for warning in report.warnings:
        print(f"note: {warning}")
    return 0


def _ingredient_report() -> int:

    with Session(get_engine()) as session:
        report = build_report(session)
    print(format_report(report))
    return 1 if report.errors else 0


def _safety_table() -> int:
    reheat = fs.LEFTOVERS_REHEAT

    print("Safe internal temperatures (CLAUDE.md USDA baseline):")
    for temp in fs.SAFE_INTERNAL_TEMPS.values():
        rest = f" + {temp.rest_minutes}-minute rest" if temp.rest_minutes else ""
        print(f"  {temp.key:16} {temp.temp_f} F{rest:18} {temp.applies_to}")
    print(f"  {reheat.key:16} {reheat.temp_f} F{'':18} {reheat.applies_to}")
    print(f"\nCooked leftovers in the fridge: {fs.LEFTOVER_FRIDGE_DAYS_DEFAULT} days (your fixed default)")
    print(f"\nStorage chart: {fs.FOODSAFETY_GOV_CHART_URL}")
    print(f"  status: {fs.CHART_ACCESS_NOTE}")
    for entry in fs.STORAGE_CHART:
        fridge = (
            f"{entry.fridge_days_min}-{entry.fridge_days_max} days"
            if entry.fridge_days_max is not None
            else "pending"
        )
        print(f"  {entry.key:22} {entry.status:9} fridge: {fridge:12} {entry.food}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Mealbro backend commands")
    sub = parser.add_subparsers(dest="command", required=True)
    usda = sub.add_parser("usda-import", help="import USDA FoodData Central CSV zips")
    usda.add_argument("paths", nargs="*", help="zip files or extracted folders (default: USDA_RAW_DIR)")
    sub.add_parser("usda-subset", help="rebuild the committed USDA test fixture")
    sub.add_parser("seed", help="load seed data (idempotent)")
    sub.add_parser("ingredient-report", help="data-quality report")
    sub.add_parser("safety-table", help="print the food-safety table with its citation")
    args = parser.parse_args(argv)
    if args.command == "usda-import":
        return _usda_import(args.paths)
    if args.command == "usda-subset":
        return _usda_subset()
    if args.command == "seed":
        return _seed()
    if args.command == "ingredient-report":
        return _ingredient_report()
    return _safety_table()


if __name__ == "__main__":
    sys.exit(main())
