"""`cli ingredient-report`: data-quality review of the seeded ingredients and seed recipes."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient
from app.domain.exclusions import PORK_COMPONENT_TAG, PORK_TRACE_TAG, ExclusionStatus
from app.domain.food_safety import STORAGE_CHART, ChartStatus
from app.domain.nutrition import CORE_CODES, atwater_kcal, atwater_mismatch
from app.seed.files import DATA_DIR, load_seed_files
from app.services.exclusions import diet_status
from app.services.ingredient_data import load_ingredients
from app.services.recipes import seed_recipes
from app.services.settings import current_user


@dataclass
class IngredientReport:
    errors: list[str] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)
    held: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    pork_capped: list[str] = field(default_factory=list)
    pork_trace: list[str] = field(default_factory=list)
    atwater_mismatches: list[str] = field(default_factory=list)
    approximate_mappings: list[str] = field(default_factory=list)
    seed_recipes: list[str] = field(default_factory=list)
    unreviewed_mappings: int = 0
    ingredient_count: int = 0


def build_report(session: Session) -> IngredientReport:
    report = IngredientReport()
    files = load_seed_files(DATA_DIR)
    user = current_user(session)
    data = load_ingredients(session)
    status = diet_status(session, user.id, data)
    report.ingredient_count = len(data)
    rows = {i.id: i for i in session.scalars(select(Ingredient))}

    expected_label_gaps = {slug: set(label.placeholders) for slug, label in files.labels.labels.items()}
    for slug, label in files.labels.labels.items():
        if label.placeholders:
            report.placeholders.append(
                f"{slug}: {', '.join(label.placeholders)} per {label.serving_unit} not filled yet "
                f"({label.source})"
            )
    for slug, package in files.labels.packages.items():
        if package.is_estimate:
            report.placeholders.append(
                f"{slug}: net weight {package.net_weight_g} g / {package.count} is an "
                f"ESTIMATE ({package.source})"
            )
    pending = [e.key for e in STORAGE_CHART if e.status is ChartStatus.PENDING]
    if pending:
        report.placeholders.append(
            f"food-safety storage chart: {len(pending)} rows pending transcription (A1)"
        )

    for ingredient_id, d in sorted(data.items(), key=lambda kv: kv[1].slug):
        result = status.results[ingredient_id]
        tags = d.tagged.diet_tags
        missing_core = [c for c in CORE_CODES if c not in d.profile.per_100g]
        gap = f" (USDA has no {', '.join(missing_core)} yet)" if missing_core else ""
        if result.status is ExclusionStatus.HELD:
            report.held.append(f"{d.name}: {rows[ingredient_id].diet_review_note}{gap}")
        elif result.status is ExclusionStatus.EXCLUDED:
            report.excluded.append(f"{d.name}: {'; '.join(result.reasons)}{gap}")
        if PORK_COMPONENT_TAG in tags:
            report.pork_capped.append(d.name)
        if PORK_TRACE_TAG in tags:
            report.pork_trace.append(d.name)
        notes = rows[ingredient_id].notes or ""
        if "APPROXIMATE" in notes:
            report.approximate_mappings.append(f"{d.name}: {notes}")
        if d.nutrition_source == "usda" and rows[ingredient_id].nutrition_reviewed_at is None:
            report.unreviewed_mappings += 1

        if missing_core:
            # label placeholders are listed above; unusable items were annotated in their own section
            expected = expected_label_gaps.get(d.slug, set())
            if result.usable and not set(missing_core) <= expected:
                report.errors.append(f"{d.name}: usable but missing core nutrition {', '.join(missing_core)}")
            continue
        p = d.profile.per_100g
        fiber = p.get("fiber_g")
        if atwater_mismatch(p["energy_kcal"], p["protein_g"], p["carbohydrate_g"], p["fat_g"], fiber):
            computed = atwater_kcal(p["protein_g"], p["carbohydrate_g"], p["fat_g"], fiber)
            report.atwater_mismatches.append(
                f"{d.name}: stated {p['energy_kcal']:.0f} kcal vs 4/4/9 = {computed:.0f} kcal per 100 g"
            )

    for view in seed_recipes(session, user.id):
        calc = view.calculation
        state = "complete" if calc.nutrition_complete else "INCOMPLETE: " + "; ".join(calc.incomplete_reasons)
        report.seed_recipes.append(f"{view.version.title} (draft v{view.version.version_number}): {state}")
        for line in calc.lines:
            if not status.results[line.ingredient.id].usable:
                report.errors.append(
                    f"seed recipe '{view.version.title}' uses unusable {line.ingredient.name}"
                )
    return report


def format_report(report: IngredientReport) -> str:
    def section(title: str, items: list[str]) -> list[str]:
        return (
            [f"\n{title} ({len(items)})", *[f"  - {item}" for item in items]] if items else [f"\n{title} (0)"]
        )

    lines = [f"Ingredient report: {report.ingredient_count} ingredients"]
    lines += section("ERRORS", report.errors)
    lines += section("Expected placeholders (fill from labels / sources)", report.placeholders)
    lines += section("Held: excluded by default until you allow them (possible beef)", report.held)
    lines += section("Excluded", report.excluded)
    lines += section("Pork meal components (frequency-capped)", report.pork_capped)
    lines += section("Trace pork (allowed, unlimited)", report.pork_trace)
    lines += section("Approximate USDA mappings", report.approximate_mappings)
    lines += section("Atwater mismatches > 20% (check the mapping)", report.atwater_mismatches)
    lines += section("Seed recipes", report.seed_recipes)
    lines.append(f"\nUSDA mappings not yet reviewed by you: {report.unreviewed_mappings}")
    return "\n".join(lines)
