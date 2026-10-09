"""`cli mapping-review`: the USDA mapping review sheet (docs/review/usda_mappings.md).

Every mapped ingredient, sorted by its share of the calories in all seed recipes (highest first), with
auto-flags for state mismatches and for USDA descriptions that contradict how the ingredient is used.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient, IngredientAlias, Product, Recipe, RecipeIngredient
from app.domain.enums import NutritionSource, RecipeOrigin
from app.domain.food_state import FoodState, line_state_error
from app.domain.nutrition import CORE_CODES
from app.domain.units import grams_of
from app.services.ingredient_data import IngredientData, load_ingredients

REVIEW_TOP_N = 25
REVIEW_MARK = "Krish to review"
STATE_LABELS = {
    FoodState.RAW: "raw",
    FoodState.DRY: "dry",
    FoodState.COOKED: "cooked",
    FoodState.AS_SOLD: "as-sold",
}

# Description keywords that need a look when the ingredient (its name, aliases, products) implies otherwise.
_KEYWORDS: dict[str, re.Pattern[str]] = {
    "fried": re.compile(r"\b(fried|pan-fried|deep-fried)\b"),
    "breaded": re.compile(r"\bbreaded\b"),
    "with skin": re.compile(r"\b(with skin|meat and skin)\b"),
    "cooked": re.compile(r"\bcooked\b"),
    "canned": re.compile(r"\bcanned\b"),
    "sweetened": re.compile(r"\bsweetened\b"),  # 'unsweetened' doesn't match: no word boundary
}
_SKIN_CONTRADICTION = re.compile(r"\b(skinless|without skin|peeled)\b")


def keyword_flags(description: str, category: str, implied: str) -> list[str]:
    """Flags for one USDA description. `implied` is the ingredient's own name, aliases and product names,
    lowercased: what the recipes mean when they use it."""
    text = description.lower()
    flags = []
    for keyword, pattern in _KEYWORDS.items():
        if not pattern.search(text):
            continue
        if keyword == "with skin":
            contradicts = bool(_SKIN_CONTRADICTION.search(implied)) or (
                category == "protein" and "skin" not in implied.replace("skinless", "")
            )
        elif keyword == "canned":
            contradicts = not re.search(r"\b(canned|can)\b", implied)
        else:
            contradicts = not re.search(rf"\b{re.escape(keyword)}\b", implied)
        if contradicts:
            flags.append(f"description says '{keyword}'")
    return flags


def state_flags(name: str, usage: Iterable[FoodState | None], mapped: FoodState) -> list[str]:
    """One flag per way the recipes use the ingredient that disagrees with the mapping's state."""
    flags = []
    for usage_state in sorted(set(usage), key=str):
        if line_state_error(name, usage_state, mapped):
            used = usage_state.value if usage_state else "raw / dry / as-sold"
            flags.append(f"state: mapping is {STATE_LABELS[mapped]}, recipes use {used} weights")
    return flags


@dataclass
class MappingRow:
    ingredient: IngredientData
    source: str
    description: str | None
    fdc_id: int | None
    state: FoodState
    kcal_per_100g: Decimal | None
    seed_kcal: Decimal
    share_pct: Decimal = Decimal(0)
    flags: list[str] = field(default_factory=list)
    review: bool = False  # top N and not approved yet
    approved_on: date | None = None


def seed_calories(session: Session, data: dict[int, IngredientData]) -> dict[int, Decimal]:
    """kcal each ingredient contributes across every seed recipe (base servings, optional lines excluded)."""
    totals: dict[int, Decimal] = defaultdict(Decimal)
    rows = session.execute(
        select(RecipeIngredient.ingredient_id, RecipeIngredient.quantity, RecipeIngredient.unit)
        .join(Recipe, Recipe.default_version_id == RecipeIngredient.recipe_version_id)
        .where(Recipe.origin == RecipeOrigin.SEED.value, RecipeIngredient.is_optional.is_(False))
    )
    for ingredient_id, quantity, unit in rows:
        d = data[ingredient_id]
        kcal = d.profile.per_100g.get("energy_kcal")
        if kcal is None:
            continue
        grams = grams_of(quantity, unit, d.units) * d.profile.edible_fraction
        totals[ingredient_id] += grams * kcal / 100
    return totals


def _implied_text(session: Session) -> dict[int, str]:
    parts: dict[int, list[str]] = defaultdict(list)
    for ingredient_id, alias in session.execute(select(IngredientAlias.ingredient_id, IngredientAlias.alias)):
        parts[ingredient_id].append(alias)
    for ingredient_id, name in session.execute(select(Product.ingredient_id, Product.name)):
        parts[ingredient_id].append(name)
    for ingredient_id, name in session.execute(select(Ingredient.id, Ingredient.name)):
        parts[ingredient_id].append(name)
    return {i: " | ".join(p).lower() for i, p in parts.items()}


def _source_label(d: IngredientData) -> str:
    if d.nutrition_source == NutritionSource.PACKAGE_LABEL:
        return "package label (+ USDA for nutrients not on the label)" if d.fdc_id else "package label"
    return "USDA"


def build_rows(session: Session) -> list[MappingRow]:
    data = load_ingredients(session)
    kcal = seed_calories(session, data)
    total = sum(kcal.values(), Decimal(0))
    implied = _implied_text(session)
    notes = dict(session.execute(select(Ingredient.id, Ingredient.notes)).tuples().all())
    reviewed = dict(session.execute(select(Ingredient.id, Ingredient.nutrition_reviewed_at)).tuples().all())
    rows = []
    for d in data.values():
        usage: list[FoodState | None] = [None]  # recipe quantities default to raw / dry / as-sold
        row = MappingRow(
            ingredient=d,
            source=_source_label(d),
            description=d.usda_description,
            fdc_id=d.fdc_id,
            state=d.mapping_state,
            kcal_per_100g=d.profile.per_100g.get("energy_kcal"),
            seed_kcal=kcal.get(d.id, Decimal(0)),
        )
        if (reviewed_at := reviewed.get(d.id)) is not None:
            row.approved_on = reviewed_at.date()
        row.share_pct = (
            (row.seed_kcal / total * 100).quantize(Decimal("0.1"), ROUND_HALF_UP) if total else Decimal(0)
        )
        row.flags = state_flags(d.name, usage, row.state)
        if d.nutrition_source == NutritionSource.USDA and d.usda_description:
            row.flags += keyword_flags(d.usda_description, d.category, implied.get(d.id, ""))
        if missing := [c for c in CORE_CODES if c not in d.profile.per_100g]:
            row.flags.append(f"note: no {', '.join(missing)} in the mapping")
        if "APPROXIMATE" in (notes.get(d.id) or ""):
            row.flags.append("note: approximate mapping (no exact USDA food)")
        rows.append(row)
    rows.sort(key=lambda r: (-r.seed_kcal, r.ingredient.name))
    for row in rows[:REVIEW_TOP_N]:
        row.review = row.approved_on is None
    return rows


def flag_summary(rows: Sequence[MappingRow]) -> list[str]:
    flagged = [r for r in rows if r.flags]
    lines = []
    by_kind: dict[str, list[str]] = defaultdict(list)
    for r in flagged:
        for flag in r.flags:
            by_kind[flag].append(r.ingredient.name)
    for kind, names in sorted(by_kind.items()):
        lines.append(f"{kind}: {len(names)} ({', '.join(names)})")
    return lines


def _cell(text: str | None) -> str:
    return (text or "—").replace("|", "/")


def render_markdown(rows: Sequence[MappingRow], generated_on: date) -> str:
    out = [
        "# USDA mapping review",
        "",
        f"Generated {generated_on.isoformat()} by `uv run python -m app.cli mapping-review` from the seeded "
        "database. Regenerate after changing mappings; don't edit this file by hand.",
        "",
        "- **Sorted by** each ingredient's share of the calories in all seed recipes (base servings, "
        "optional lines excluded), highest first. Ingredients no seed uses come last, alphabetically.",
        "- **State** is the state the nutrition mapping describes, read from the USDA description "
        "(package labels are as-sold). Recipe quantities are raw / dry / as-sold weights unless a line says "
        "otherwise.",
        "- **Auto-flags:** `state:` = the mapping's state doesn't match how recipes use it. "
        "`description says '…'` = the USDA description contains fried / breaded / with skin / cooked / "
        "canned / sweetened while the ingredient's name, aliases and products imply otherwise. Package-label "
        "ingredients aren't checked for description issues. `note:` = other things worth a look.",
        f"- The top {REVIEW_TOP_N} rows are marked **{REVIEW_MARK}** until you approve them; approved rows "
        "show the approval date.",
        "",
        "## Flag summary",
        "",
    ]
    summary = flag_summary(rows)
    out += [f"- {line}" for line in summary] if summary else ["- No flags."]
    out += [
        "",
        f"## Mappings ({len(rows)})",
        "",
        "| # | Ingredient | Nutrition source | USDA description | FDC id | State | kcal per 100 g "
        "| % of seed calories | Flags |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rank, r in enumerate(rows, start=1):
        marks = [f"approved {r.approved_on.isoformat()}"] if r.approved_on else []
        marks += [f"**{REVIEW_MARK}**"] if r.review else []
        flags = marks + r.flags
        kcal = f"{r.kcal_per_100g:.0f}" if r.kcal_per_100g is not None else "—"
        out.append(
            f"| {rank} | {_cell(r.ingredient.name)} | {r.source} | {_cell(r.description)} | "
            f"{r.fdc_id or '—'} | {STATE_LABELS[r.state]} | {kcal} | {r.share_pct}% "
            f"| {_cell('; '.join(flags))} |"
        )
    return "\n".join(out) + "\n"
