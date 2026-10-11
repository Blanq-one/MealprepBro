"""Checks every generated recipe before it is persisted (deliverable 9). Each failure is a short message the
LLM can act on in a retry.

  * every ingredient resolves, and none is excluded or held (resolver);
  * step text never names an excluded food (beef broth, tallow, unspecified gelatin, …) — an exclusion error;
  * step text never uses an ingredient missing from the list ("add 2 strips of bacon") — an
    unlisted-ingredient error, not an exclusion (staples like salt and water are exempt);
  * raw / dry / as-sold state of every line matches its nutrition mapping (§7.8);
  * units are valid for the ingredient (named units must exist; volume needs a density, count a piece weight);
  * per-serving amounts are plausible;
  * equipment ⊆ what you have; hands-on time fits the mood;
  * the prose filter (§7.3) on every displayed text.
A recipe with poultry, meat, fish or an egg dish but no doneness step gets one appended (not an error).

Ideas (Phase 2b, FLOW_SPEC §13.5) get every check here except the step checks (`validate_idea`); an idea and
its steps are later validated together as one GeneratedRecipe.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.cook_time import mood_time_error
from app.domain.enums import Equipment, InstructionSection, RecipeMood
from app.domain.food_safety import IngredientSafety, doneness_requirement
from app.domain.food_state import line_state_error
from app.domain.text_rules import check_text
from app.domain.units import UnitError, grams_of, normalize_unit, to_base
from app.planning.resolver import IngredientResolver, Resolution
from app.schemas.llm_recipe import GeneratedRecipe, IdeaIngredient, LLMIngredient, RecipeIdea
from app.seed.files import normalize_name

# Upper bounds on grams per serving, by ingredient category (raw / dry / as sold).
MAX_GRAMS_PER_SERVING = {
    "protein": Decimal(450),
    "grain": Decimal(250),
    "legume": Decimal(250),
    "vegetable": Decimal(600),
    "fruit": Decimal(400),
    "dairy": Decimal(500),
    "fat_oil": Decimal(45),
    "nut_seed": Decimal(80),
    "spice": Decimal(15),
    "condiment": Decimal(150),
    "sweetener": Decimal(60),
    "supplement": Decimal(70),
    "beverage": Decimal(750),
    "other": Decimal(100),
}
MAX_TOTAL_GRAMS_PER_SERVING = Decimal(1600)
BEEF_WORDS = re.compile(r"\b(beef|veal|bovine|tallow)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ResolvedLine:
    ingredient_id: int
    name: str  # canonical
    written_name: str
    quantity: Decimal  # base quantity (g / ml / count) for base_servings
    unit: str
    authored_quantity: Decimal
    authored_unit: str
    preparation: str | None
    role: str
    component: str | None
    optional: bool
    substituted_from: str | None = None


@dataclass(frozen=True)
class ResolvedStep:
    section: str
    text: str
    duration_minutes: int | None
    appliance_temp_f: int | None
    doneness_check_ingredient_id: int | None
    added_by_app: bool = False


@dataclass(frozen=True)
class ValidatedRecipe:
    recipe: GeneratedRecipe
    lines: tuple[ResolvedLine, ...]
    steps: tuple[ResolvedStep, ...]
    appended_safety_step: bool


class StepScanner:
    """Finds ingredient mentions in step text using the alias table (longest alias first)."""

    def __init__(self, resolver: IngredientResolver) -> None:
        self.resolver = resolver
        aliases = sorted(resolver.aliases, key=len, reverse=True)
        self._pattern = re.compile(
            r"(?<![a-z0-9%])(" + "|".join(re.escape(a) for a in aliases) + r")(?![a-z0-9%])"
        )

    def mentions(self, text: str) -> list[tuple[str, int]]:
        normalized = normalize_name(text)
        return [(m.group(1), self.resolver.aliases[m.group(1)]) for m in self._pattern.finditer(normalized)]


def _covers(alias: str, names: Iterable[str]) -> bool:
    """A generic mention ('chicken', 'yogurt') is fine when a listed ingredient's name contains it."""
    words = alias.split()
    for name in names:
        tokens = normalize_name(name).split()
        if any(tokens[i : i + len(words)] == words for i in range(len(tokens) - len(words) + 1)):
            return True
    return False


@dataclass(frozen=True)
class ValidatedIdea:
    idea: RecipeIdea
    lines: tuple[ResolvedLine, ...]


def check_lines(
    items: Sequence[LLMIngredient | IdeaIngredient],
    base_servings: int,
    resolver: IngredientResolver,
) -> tuple[list[ResolvedLine], dict[str, Resolution], list[str]]:
    """Names, units, the raw / dry / as-sold rule, plausible amounts, duplicate lines and total food per
    serving. Returns (lines, how each name resolved, errors)."""
    errors: list[str] = []
    lines: list[ResolvedLine] = []
    resolutions: dict[str, Resolution] = {}
    for item in items:
        res = resolver.resolve(item.name)
        resolutions[item.name] = res
        if not res.ok:
            errors.append(res.error or f"'{item.name}' could not be resolved")
            continue
        assert res.ingredient_id is not None
        data = resolver.data[res.ingredient_id]
        try:
            unit = normalize_unit(item.unit.value, data.units.named_units)
            quantity = Decimal(str(item.quantity))
            base = to_base(quantity, unit, data.units)
            grams = grams_of(base.amount, base.unit.value, data.units)
        except UnitError as exc:
            hint = "use g" if data.units.default_unit_kind == "mass" else "use a listed unit"
            errors.append(
                f"{item.name}: unit '{item.unit.value}' can't be used for {data.name} ({exc}); {hint}"
            )
            continue
        if problem := line_state_error(data.name, None, data.mapping_state):
            errors.append(problem)
        per_serving = grams / Decimal(base_servings)
        cap = MAX_GRAMS_PER_SERVING.get(data.category, Decimal(300))
        if per_serving > cap:
            errors.append(
                f"{item.name}: {per_serving:.0f} g per serving is implausible for {data.category} "
                f"(at most {cap} g); check the quantity is for all {base_servings} servings"
            )
        lines.append(
            ResolvedLine(
                ingredient_id=res.ingredient_id,
                name=data.name,
                written_name=item.name,
                quantity=base.amount,
                unit=base.unit.value,
                authored_quantity=quantity,
                authored_unit=unit,
                preparation=getattr(item, "preparation", None),
                role=item.role.value,
                component=getattr(item, "component", None),
                optional=getattr(item, "optional", False),
                substituted_from=res.substituted_from,
            )
        )
    ids = [ln.ingredient_id for ln in lines]
    if len(set(ids)) != len(ids):
        dupes = sorted({resolver.data[i].name for i in ids if ids.count(i) > 1})
        errors.append(f"these lines are the same ingredient, combine them: {', '.join(dupes)}")
    total = sum(
        (
            grams_of(ln.quantity, ln.unit, resolver.data[ln.ingredient_id].units)
            for ln in lines
            if not ln.optional
        ),
        Decimal(0),
    )
    if total / Decimal(base_servings) > MAX_TOTAL_GRAMS_PER_SERVING:
        errors.append(
            f"about {total / base_servings:.0f} g of food per serving is implausible; check base_servings"
        )
    return lines, resolutions, errors


def _basics(
    used: Iterable[Equipment], equipment: frozenset[Equipment], mood: RecipeMood, active_minutes: int
) -> list[str]:
    errors = []
    if missing := sorted(set(used) - equipment):
        errors.append(f"uses equipment that isn't available: {', '.join(missing)}")
    if problem := mood_time_error(mood, active_minutes):
        errors.append(problem)
    return errors


def _prose(texts: Iterable[str]) -> list[str]:
    return [v.message for text in texts for v in check_text(text)]


def validate_idea(
    idea: RecipeIdea, resolver: IngredientResolver, equipment: frozenset[Equipment]
) -> tuple[ValidatedIdea | None, list[str]]:
    """Every recipe check except the step checks: names, units and the as-sold rule, exclusions and held
    items, plausible amounts, equipment, hands-on time for the mood, and the prose filter on the title and
    method. (Complete nutrition, caps and the request's own limits are checked by the caller.)"""
    lines, _, errors = check_lines(idea.ingredients, idea.base_servings, resolver)
    errors += _basics(idea.equipment, equipment, idea.mood, idea.active_minutes)
    errors += _prose([idea.title, idea.method])
    if errors:
        return None, list(dict.fromkeys(errors))
    return ValidatedIdea(idea, tuple(lines)), []


def validate_generated(
    recipe: GeneratedRecipe,
    resolver: IngredientResolver,
    scanner: StepScanner,
    equipment: frozenset[Equipment],
) -> tuple[ValidatedRecipe | None, list[str]]:
    lines, resolutions, errors = check_lines(recipe.ingredients, recipe.base_servings, resolver)
    errors += _basics(recipe.equipment, equipment, recipe.mood, recipe.active_minutes)
    texts = [recipe.title, recipe.description] + [i.preparation or "" for i in recipe.ingredients]
    texts += [s.text for s in recipe.steps]
    errors += _prose(texts)
    # Everything the recipe lists counts as listed for the step checks, even a line whose unit was rejected
    # above, so one bad unit doesn't cascade into "step uses an unlisted ingredient" errors.
    resolved = [(name, r) for name, r in resolutions.items() if r.ingredient_id is not None]
    listed = {r.ingredient_id for _, r in resolved if r.ingredient_id is not None}
    listed_names = [name for name, _ in resolved] + [r.canonical_name or "" for _, r in resolved]
    steps: list[ResolvedStep] = []
    for n, step in enumerate(recipe.steps, start=1):
        for word in BEEF_WORDS.findall(step.text):
            errors.append(f"step {n} mentions '{word}', which is excluded (beef); remove it")
        for alias, ingredient_id in scanner.mentions(step.text):
            status = resolver.statuses[ingredient_id].status.value
            if status != "allowed":
                if not BEEF_WORDS.search(alias):
                    errors.append(f"step {n} mentions '{alias}', which is {status}; remove it")
                continue
            data = resolver.data[ingredient_id]
            if ingredient_id in listed or data.assume_in_stock or _covers(alias, listed_names):
                continue
            errors.append(
                f"step {n} uses '{alias}', which isn't in the ingredient list; "
                "add it as an ingredient or remove it"
            )
        doneness_id = None
        if step.doneness_check_for:
            res = resolutions.get(step.doneness_check_for) or resolver.resolve(step.doneness_check_for)
            if res.ingredient_id is None or res.ingredient_id not in listed:
                errors.append(
                    f"step {n}: doneness_check_for '{step.doneness_check_for}' is not one of the ingredients"
                )
            else:
                doneness_id = res.ingredient_id
        steps.append(
            ResolvedStep(
                step.section.value, step.text, step.duration_minutes, step.appliance_temp_f, doneness_id
            )
        )
    if errors:
        return None, list(dict.fromkeys(errors))
    appended = False
    safety = [
        IngredientSafety(ln.name, resolver.data[ln.ingredient_id].safety_category, ln.role)
        for ln in lines
        if not ln.optional
    ]
    if doneness_requirement(safety) is not None and not any(s.doneness_check_ingredient_id for s in steps):
        target = max(
            (
                ln
                for ln in lines
                if resolver.data[ln.ingredient_id].safety_category is not None and not ln.optional
            ),
            key=lambda ln: ln.quantity,
        )
        cooking = [
            i
            for i, s in enumerate(steps)
            if s.section
            not in (
                InstructionSection.PORTIONING.value,
                InstructionSection.STORAGE.value,
                InstructionSection.REHEATING.value,
            )
        ]
        at = (cooking[-1] + 1) if cooking else len(steps)
        section = steps[cooking[-1]].section if cooking else InstructionSection.PREP.value
        steps.insert(
            at,
            ResolvedStep(
                section,
                f"Check the {target.name} for doneness.",
                None,
                None,
                target.ingredient_id,
                added_by_app=True,
            ),
        )
        appended = True
    return ValidatedRecipe(recipe, tuple(lines), tuple(steps), appended), []
