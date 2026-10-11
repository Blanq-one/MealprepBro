"""Recipe rendering (deliverable 11): sections, injected safety lines, code-written storage and reheating
text, "≈ X g per container", nutrient labels and the "draft" badge.

Safety values come only from domain/food_safety.py (CLAUDE.md food safety rules):
  * every step with a doneness check gets the matching safe-temperature line;
  * a recipe with a poultry / meat / fish / egg-dish ingredient but no doneness step gets one appended;
  * STORAGE and REHEATING sections end with the table's text (a STORAGE section is always present).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.domain.enums import InstructionSection
from app.domain.food_safety import (
    SAFE_INTERNAL_TEMPS,
    IngredientSafety,
    SafetyCategory,
    doneness_requirement,
    doneness_text,
    freezer_storage_text,
    fridge_storage_text,
    reheat_text,
)
from app.domain.nutrition import dv_label, kcal_display
from app.domain.quantities import format_quantity, portion_note

COOKING_SECTIONS = (
    InstructionSection.STOVETOP,
    InstructionSection.OVEN,
    InstructionSection.AIR_FRYER,
    InstructionSection.MICROWAVE,
    InstructionSection.RICE,
)
SECTION_ORDER = list(InstructionSection)
NUTRIENT_LABEL_NAMES = {
    "protein_g": "protein",
    "fiber_g": "fiber",
    "iron_mg": "iron",
    "calcium_mg": "calcium",
    "potassium_mg": "potassium",
    "vitamin_c_mg": "vitamin C",
    "vitamin_d_ug": "vitamin D",
    "vitamin_b12_ug": "vitamin B12",
    "folate_dfe_ug": "folate",
    "magnesium_mg": "magnesium",
    "zinc_mg": "zinc",
}
THAW_NOTE = "From the freezer: move it to the fridge the night before."


@dataclass(frozen=True)
class StepInput:
    section: str
    text: str
    duration_minutes: int | None = None
    appliance_temp_f: int | None = None
    doneness_check_ingredient_id: int | None = None


@dataclass(frozen=True)
class LineInput:
    ingredient_id: int
    name: str
    amount: Decimal
    unit: str
    grams: Decimal  # edible grams (bone-in cuts: the weight as purchased less USDA's refuse, M5)
    role: str
    safety_category: SafetyCategory | None = None
    preparation: str | None = None
    optional: bool = False


@dataclass(frozen=True)
class RenderInput:
    version_id: int
    title: str
    description: str
    is_draft: bool
    freezer_friendly: bool
    portions: int
    lines: Sequence[LineInput]
    steps: Sequence[StepInput]
    leftover_fridge_days: int
    per_portion: Mapping[str, Decimal]  # computed by code from the (scaled, rounded) lines
    daily_values: Mapping[str, Decimal]  # nutrient code -> FDA daily value
    heme_iron_mg: Decimal | None = None


@dataclass(frozen=True)
class RenderedStep:
    section: str
    text: str
    duration_minutes: int | None = None
    appliance_temp_f: int | None = None
    safety_note: str | None = None
    added_by_app: bool = False


@dataclass(frozen=True)
class RenderedLine:
    ingredient_id: int
    name: str
    display: str  # "1¼ tsp salt"
    preparation: str | None
    optional: bool
    amount_display: str = ""  # "1¼ tsp": the batch's amount alone
    portion_note: str | None = None  # "⅜ tsp per portion · 1¼ tsp for the batch of 4" (A1)


@dataclass(frozen=True)
class RenderedRecipe:
    version_id: int
    title: str
    description: str
    badge: str | None
    portions: int
    lines: tuple[RenderedLine, ...]
    steps: tuple[RenderedStep, ...]
    per_container: str
    labels: tuple[str, ...]
    kcal_per_portion: int
    heme_note: str | None

    @property
    def safety_notes(self) -> tuple[str, ...]:
        return tuple(s.safety_note for s in self.steps if s.safety_note)


def _safety_lines(lines: Sequence[LineInput]) -> list[IngredientSafety]:
    return [IngredientSafety(ln.name, ln.safety_category, ln.role) for ln in lines if not ln.optional]


def _doneness_for(line: LineInput) -> str | None:
    if line.safety_category is None:
        return None
    return doneness_text(line.name, SAFE_INTERNAL_TEMPS[line.safety_category])


def render(data: RenderInput) -> RenderedRecipe:
    by_id = {ln.ingredient_id: ln for ln in data.lines}
    steps: list[RenderedStep] = []
    has_doneness = False
    for step in data.steps:
        note = None
        if step.doneness_check_ingredient_id is not None and step.doneness_check_ingredient_id in by_id:
            note = _doneness_for(by_id[step.doneness_check_ingredient_id])
            has_doneness = has_doneness or note is not None
        steps.append(
            RenderedStep(step.section, step.text, step.duration_minutes, step.appliance_temp_f, note)
        )
    requirement = doneness_requirement(_safety_lines(data.lines))
    if requirement is not None and not has_doneness:
        strictest = max(
            (ln for ln in data.lines if ln.safety_category is not None and not ln.optional),
            key=lambda ln: (SAFE_INTERNAL_TEMPS[ln.safety_category].temp_f, ln.grams),  # type: ignore[index]
        )
        last_cooking = max(
            (i for i, s in enumerate(steps) if s.section in COOKING_SECTIONS),
            default=len(steps) - 1,
        )
        steps.insert(
            last_cooking + 1,
            RenderedStep(
                steps[last_cooking].section if steps else InstructionSection.PREP.value,
                f"Check the {strictest.name} for doneness before portioning.",
                safety_note=doneness_text(strictest.name, requirement),
                added_by_app=True,
            ),
        )
    storage = fridge_storage_text(data.leftover_fridge_days)
    if data.freezer_friendly:
        storage += " " + freezer_storage_text()
    if not any(s.section == InstructionSection.STORAGE for s in steps):
        steps.append(RenderedStep(InstructionSection.STORAGE.value, storage, added_by_app=True))
    else:
        last = max(i for i, s in enumerate(steps) if s.section == InstructionSection.STORAGE)
        steps.insert(last + 1, RenderedStep(InstructionSection.STORAGE.value, storage, added_by_app=True))
    reheating = [i for i, s in enumerate(steps) if s.section == InstructionSection.REHEATING]
    if reheating:
        steps.insert(
            reheating[-1] + 1,
            RenderedStep(InstructionSection.REHEATING.value, reheat_text(), added_by_app=True),
        )
    elif any(s.section in COOKING_SECTIONS for s in steps):
        steps.append(RenderedStep(InstructionSection.REHEATING.value, reheat_text(), added_by_app=True))
    steps.sort(key=lambda s: _section_rank(s.section))
    grams = sum((ln.grams for ln in data.lines if not ln.optional), Decimal(0))
    per_container = (grams / Decimal(data.portions) / 10).quantize(Decimal(1), ROUND_HALF_UP) * 10
    labels = []
    for code, name in NUTRIENT_LABEL_NAMES.items():
        if code in data.per_portion and code in data.daily_values:
            label = dv_label(data.per_portion[code], data.daily_values[code])
            if label == "high_in":
                labels.append(f"High in {name}")
            elif label == "good_source":
                labels.append(f"Good source of {name}")
    heme_note = None
    if data.heme_iron_mg is not None and data.per_portion.get("iron_mg"):
        heme = data.heme_iron_mg.quantize(Decimal("0.1"), ROUND_HALF_UP)
        non_heme = (data.per_portion["iron_mg"] - data.heme_iron_mg).quantize(Decimal("0.1"), ROUND_HALF_UP)
        heme_note = f"Iron: about {heme} mg heme and {non_heme} mg non-heme per portion (estimated)"
    return RenderedRecipe(
        version_id=data.version_id,
        title=data.title,
        description=data.description,
        badge="draft" if data.is_draft else None,
        portions=data.portions,
        lines=tuple(
            RenderedLine(
                ln.ingredient_id,
                ln.name,
                f"{format_quantity(ln.amount, ln.unit)} {ln.name}",
                ln.preparation,
                ln.optional,
                format_quantity(ln.amount, ln.unit),
                portion_note(ln.amount, ln.unit, data.portions),
            )
            for ln in data.lines
        ),
        steps=tuple(steps),
        per_container=f"≈ {per_container} g per container",
        labels=tuple(labels),
        kcal_per_portion=kcal_display(data.per_portion.get("energy_kcal", Decimal(0))),
        heme_note=heme_note,
    )


def _section_rank(section: str) -> int:
    """Keep the author's order for cooking steps; portioning, storage and reheating come last."""
    tail = {
        InstructionSection.PORTIONING.value: 1,
        InstructionSection.STORAGE.value: 2,
        InstructionSection.REHEATING.value: 3,
    }
    return tail.get(section, 0)
