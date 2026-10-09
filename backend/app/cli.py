"""Command line: `uv run python -m app.cli <command>`.

usda-import [PATH ...]   import USDA FoodData Central CSV zips (default: every zip in USDA_RAW_DIR)
usda-subset              rebuild the committed test fixture from the full zips
seed                     load seed data (idempotent; run after usda-import)
ingredient-report        data-quality report: errors, placeholders, held items, Atwater mismatches
safety-table             print the hardcoded food-safety table and its citation
plan-week [--mode M]     plan a week from your current settings and print it (Phase 1 demo)
simulate-weeks           dry run: plan consecutive weeks, each from the last one's leftovers
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.db.models import RecipeVersion
from app.db.session import get_engine
from app.domain import food_safety as fs
from app.domain import storage_chart
from app.domain.enums import CalorieMode, MealSlot, NutritionPriority, PlanningMode
from app.llm.client import make_client
from app.llm.errors import LLMConfigError
from app.planning.persistence import accept_plan
from app.planning.text_report import format_failure, format_plan
from app.schemas.plans import DayOverride, PlanRequest
from app.seed.files import load_seed_files
from app.seed.loader import seed_all
from app.seed.mapping_review import build_rows, flag_summary, render_markdown
from app.seed.report import build_report, format_report
from app.services.plans import run_plan_now
from app.services.pricing import active_stores
from app.services.settings import current_user
from app.services.simulation import format_table, simulate
from app.usda.importer import import_release
from app.usda.release import find_releases
from app.usda.subset import build_subset

PRIORITIES = ["protein", "carb", "iron", "balanced"]
WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

REVIEW_SHEET = BACKEND_DIR.parent / "docs" / "review" / "usda_mappings.md"
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


def _mapping_review(out: Path) -> int:
    with Session(get_engine()) as session:
        rows = build_rows(session)
    out.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).astimezone().date()
    out.write_text(render_markdown(rows, today), encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(rows)} ingredients)")
    for line in flag_summary(rows):
        print(f"  {line}")
    return 0


def _safety_table() -> int:
    reheat = fs.LEFTOVERS_REHEAT
    print("Safe internal temperatures (CLAUDE.md USDA baseline):")
    for temp in fs.SAFE_INTERNAL_TEMPS.values():
        rest = f" + {temp.rest_minutes}-minute rest" if temp.rest_minutes else ""
        print(f"  {temp.key:16} {temp.temp_f} F{rest:18} {temp.applies_to}")
    print(f"  {reheat.key:16} {reheat.temp_f} F{'':18} {reheat.applies_to}")
    leftovers = fs.storage_for("cooked_leftovers")
    print(
        f"\nCooked leftovers: {fs.LEFTOVER_FRIDGE_DAYS_DEFAULT} days in the fridge (your default; chart: "
        f"{leftovers.refrigerator}, so the setting can go up to {fs.leftover_fridge_days_upper_bound()})"
    )
    print(
        "\nStorage: FoodSafety.gov Cold Food Storage Chart, "
        f"last reviewed {storage_chart.CHART_LAST_REVIEWED}"
    )
    print(f"  {storage_chart.CHART_URL}")
    print(f"  saved copy: {storage_chart.CHART_PDF} ({storage_chart.CHART_SAVED_ON})")
    print(f"  {storage_chart.FREEZER_NOTE}")
    food = None
    for row in storage_chart.STORAGE_CHART:
        if row.food != food:
            food = row.food
            print(f"\n  {food}")
        print(f"    {row.type[:58]:58}  fridge: {row.refrigerator:30}  freezer: {row.freezer}")
    return 0


def _next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def _simulate_weeks(args: argparse.Namespace) -> int:
    week_start = args.week or _next_monday(datetime.now(UTC).astimezone().date())
    with Session(get_engine()) as session:
        user = current_user(session)
        sim = simulate(
            session,
            user.id,
            week_start,
            args.weeks,
            budget_cents=_cents(args.budget),
            last_week_budget_cents=_cents(args.last_week_budget),
        )
        print(format_table(sim))
        for n, carried in enumerate(sim.carried, start=1):
            print()
            print(f"Carried from week {n} into week {n + 1} (at-risk perishables are not carried):")
            for lot in carried:
                print(f"  {lot.name:40} {lot.quantity.quantize(Decimal(1)):>8} {lot.unit:5} {lot.location}")
        for run in sim.runs:
            if run.plan is None:
                print()
                print(f"{run.label}: {format_failure(run.outcome)}")
            else:
                for note in (n for n in run.plan.notes if n.startswith("Your budget is tight")):
                    print()
                    print(f"{run.label}: {note}")
        session.rollback()
    print()
    print("(dry run: nothing was saved)")
    return 0 if all(run.plan is not None for run in sim.runs) else 1


def _cents(dollars: float | None) -> int | None:
    return round(dollars * 100) if dollars is not None else None


def _plan_week(args: argparse.Namespace) -> int:
    slot_kcal: dict[MealSlot, int] = {}
    for item in args.slot or []:
        name, _, kcal = item.partition("=")
        try:
            slot_kcal[MealSlot(name.strip())] = int(kcal)
        except ValueError:
            print(f"--slot needs slot=kcal with a known slot, got '{item}'", file=sys.stderr)
            return 2
    week_start = args.week or _next_monday(datetime.now(UTC).astimezone().date())
    overrides: list[DayOverride] = []
    for item in args.minutes or []:
        name, _, minutes = item.partition("=")
        if name.strip().lower() not in WEEKDAY_NAMES or not minutes.strip().isdigit():
            print(f"--minutes needs weekday=minutes (e.g. mon=60), got '{item}'", file=sys.stderr)
            return 2
        offset = (WEEKDAY_NAMES.index(name.strip().lower()) - week_start.weekday()) % 7
        overrides.append(DayOverride(day=week_start + timedelta(days=offset), cook_minutes=int(minutes)))
    mode = PlanningMode(args.mode)
    if mode is PlanningMode.INVENTORY and args.budget is not None:
        print("--budget is for shop mode; in inventory mode use --topup", file=sys.stderr)
        return 2
    if mode is PlanningMode.SHOP and args.topup is not None:
        print("--topup is for inventory mode; in shop mode use --budget", file=sys.stderr)
        return 2
    request = PlanRequest(
        week_start=week_start,
        days=args.days,
        day_overrides=overrides,
        slot_kcal=slot_kcal,
        nutrition_priority=NutritionPriority(args.priority) if args.priority else None,
        secondary_priority=NutritionPriority(args.secondary) if args.secondary else None,
        calorie_mode=CalorieMode(args.calorie_mode) if args.calorie_mode else None,
        mode=mode,
        budget_cents=_cents(args.budget),
        topup_cents=_cents(args.topup),
        protein_target_g=args.protein,
        allow_llm=not args.no_llm,
    )
    client = None
    if not args.no_llm:
        try:
            client = make_client(get_settings())
        except LLMConfigError as exc:
            print(f"note: {exc}; planning from saved recipes only (pass --no-llm to hide this note)")
            request = request.model_copy(update={"allow_llm": False})
    with Session(get_engine()) as session:
        user = current_user(session)
        outcome = run_plan_now(session, user.id, request, client)
        if outcome.status == "succeeded" and outcome.plan is not None:
            if args.accept and outcome.plan_id is not None:
                accept_plan(session, user.id, outcome.plan_id)
            stores = {s.id: s.name for s in active_stores(session)}
            versions = [b.version_id for b in outcome.plan.batches]
            drafts = set(
                session.scalars(
                    select(RecipeVersion.id).where(
                        RecipeVersion.id.in_(versions), RecipeVersion.is_draft.is_(True)
                    )
                )
            )
            print(format_plan(outcome.plan, outcome, stores, drafts))
        else:
            print(format_failure(outcome))
        if args.dry_run:
            session.rollback()
            print()
            print("(dry run: nothing was saved)")
        else:
            session.commit()
    return 0 if outcome.status == "succeeded" else 1


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to a legacy code page
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Mealbro backend commands")
    sub = parser.add_subparsers(dest="command", required=True)
    usda = sub.add_parser("usda-import", help="import USDA FoodData Central CSV zips")
    usda.add_argument("paths", nargs="*", help="zip files or extracted folders (default: USDA_RAW_DIR)")
    sub.add_parser("usda-subset", help="rebuild the committed USDA test fixture")
    sub.add_parser("seed", help="load seed data (idempotent)")
    sub.add_parser("ingredient-report", help="data-quality report")
    sub.add_parser("safety-table", help="print the food-safety table with its citation")
    review = sub.add_parser("mapping-review", help="write the USDA mapping review sheet")
    review.add_argument("--out", type=Path, default=REVIEW_SHEET)
    plan = sub.add_parser("plan-week", help="plan a week from your current settings and print it")
    plan.add_argument("--week", type=date.fromisoformat, help="first day, YYYY-MM-DD (default: next Monday)")
    plan.add_argument("--days", type=int, default=7)
    plan.add_argument("--no-llm", action="store_true", help="seed and saved recipes only: zero LLM calls")
    plan.add_argument(
        "--mode",
        choices=[m.value for m in PlanningMode],
        default=PlanningMode.SHOP.value,
        help="inventory: cook from what you have; shop: inventory first, then a grocery list (default)",
    )
    plan.add_argument("--budget", type=float, help="shop mode: max cash this trip, in dollars (a hard limit)")
    plan.add_argument("--topup", type=float, help="inventory mode: dollars you allow for missing items")
    plan.add_argument("--protein", type=int, metavar="G", help="daily protein target in grams (0 = none)")
    plan.add_argument("--priority", choices=PRIORITIES)
    plan.add_argument("--secondary", choices=PRIORITIES)
    plan.add_argument("--calorie-mode", choices=["weekly", "strict_daily"])
    plan.add_argument(
        "--slot", action="append", metavar="SLOT=KCAL", help="per-plan slot allocation (0 removes)"
    )
    plan.add_argument(
        "--minutes", action="append", metavar="DAY=MIN", help="hands-on minutes for one weekday (mon=60)"
    )
    plan.add_argument("--accept", action="store_true", help="make the new plan the week's active plan")
    plan.add_argument("--dry-run", action="store_true", help="print the plan but save nothing")
    sim = sub.add_parser(
        "simulate-weeks", help="dry run: consecutive weeks, each from the last one's leftovers"
    )
    sim.add_argument(
        "--week", type=date.fromisoformat, help="first week's Monday, YYYY-MM-DD (default: next)"
    )
    sim.add_argument("--weeks", type=int, default=2)
    sim.add_argument("--budget", type=float, help="shop-mode budget for regular groceries, every week")
    sim.add_argument(
        "--last-week-budget",
        type=float,
        help="also plan the last week again from the same inventory with this budget",
    )
    args = parser.parse_args(argv)
    if args.command == "usda-import":
        return _usda_import(args.paths)
    if args.command == "usda-subset":
        return _usda_subset()
    if args.command == "seed":
        return _seed()
    if args.command == "ingredient-report":
        return _ingredient_report()
    if args.command == "mapping-review":
        return _mapping_review(args.out)
    if args.command == "plan-week":
        return _plan_week(args)
    if args.command == "simulate-weeks":
        return _simulate_weeks(args)
    return _safety_table()


if __name__ == "__main__":
    sys.exit(main())
