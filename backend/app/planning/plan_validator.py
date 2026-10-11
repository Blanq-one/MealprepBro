"""The plan validator (deliverable 15). It accepts ONLY a RoundedPlan and recomputes every number from the
reference data (a fresh database load), never from solver variables:

  quantities (practical rounding re-derived from the recipe lines and the batch scale), meal kcal, day and
  week totals per calorie mode, the protein target per calorie mode, every planned slot filled once,
  batches only on cook days, the fridge window, portions, equipment, hands-on minutes, mood, the variety
  cap, exclusions, frequency caps, inventory use, ingredients covered by inventory or the list, the
  purchase limit (shop-mode budget or inventory-mode top-up), the cost summary, the "freeze on shopping
  day" instructions for raw protein, food-safety lines and the prose filter.

Hard errors about calories, protein or the purchase limit can be fixed by a re-solve with that bound
tightened; the orchestrator does that (≤ 2 times).
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from app.domain.cook_schedule import fallback_timing, minutes_text
from app.domain.cook_time import mood_allows
from app.domain.enums import CalorieMode, MealSlot, PlanningMode
from app.domain.food_safety import IngredientSafety, doneness_requirement
from app.domain.frequency_caps import Meal, weekly_cap_violations
from app.domain.frequency_caps import ResolvedCap as DomainCap
from app.domain.nutrition import kcal_display
from app.domain.quantities import format_fraction
from app.domain.scaling import scale_line
from app.domain.text_rules import check_text
from app.domain.units import convert, grams_of, to_base
from app.planning.costing import cost_summary
from app.planning.grocery_list import build_grocery
from app.planning.perishables import freeze_instructions
from app.planning.problem import size_multiplier
from app.planning.recipe_math import nutrition_of
from app.planning.reference import ReferenceData, RefRecipe
from app.planning.rendering import LineInput, RenderInput, render
from app.planning.rounded import ABSORBED, RoundedBatch, RoundedPlan
from app.planning.timing import day_schedules, dish_batch
from app.schemas.constraints import VARIETY_CAPPED_SLOTS, ResolvedDailyCap

QTY_TOLERANCE = Decimal("0.001")
_PROTEIN = Decimal("0.1")
SCALE_TOLERANCE = Decimal("0.0001")
ABSORBED_TOLERANCE = {"g": Decimal(10), "ml": Decimal(10), "count": Decimal(1)}

Scope = Literal["week", "single"]

# Errors a re-solve with a tightened bound can fix.
RESOLVABLE = frozenset(
    {
        "KCAL_DAY_OVER_CEILING",
        "KCAL_DAY_UNDER_FLOOR",
        "KCAL_WEEK_OVER_CEILING",
        "KCAL_WEEK_UNDER_FLOOR",
        "PROTEIN_DAY_UNDER_TARGET",
        "PROTEIN_WEEK_UNDER_TARGET",
        "PURCHASE_LIMIT_OVER",
        "PURCHASE_NOT_ALLOWED",  # rounding spilled past your stock in "Use what I have" (step 2b.5)
        "DAILY_AMOUNT_OVER",  # rounding pushed a day past a daily amount cap (step 2b.5)
    }
)
AMOUNT_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    day: date | None = None
    amount: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.day is not None:
            out["day"] = self.day.isoformat()
        if self.amount is not None:
            out["amount"] = self.amount
        if self.details:
            out["details"] = dict(self.details)
        return out


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[Issue, ...]
    warnings: tuple[Issue, ...]
    day_kcal: Mapping[date, int]
    week_kcal: int
    cost_cents: int

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def resolvable(self) -> bool:
        return bool(self.errors) and all(e.code in RESOLVABLE for e in self.errors)

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [e.to_json() for e in self.errors],
            "warnings": [w.to_json() for w in self.warnings],
            "recomputed": {
                "day_kcal": {d.isoformat(): k for d, k in sorted(self.day_kcal.items())},
                "week_kcal": self.week_kcal,
                "cost_cents": self.cost_cents,
            },
        }


def _qty(quantity: Decimal, unit: str) -> str:
    if unit == "count":
        return format_fraction(quantity.quantize(Decimal("0.5"), ROUND_HALF_UP))
    return f"{quantity.quantize(Decimal(1), ROUND_HALF_UP)} {unit}"


def _day(d: date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _cap_amount(amount: Decimal, cap: ResolvedDailyCap) -> str:
    """'2 scoops (62 g)' for a cap with a display unit, else '62 g'."""
    base = f"{amount.quantize(Decimal(1), ROUND_HALF_UP)} {cap.unit}"
    if cap.display_unit and cap.unit_size:
        n = (amount / cap.unit_size).quantize(Decimal("0.1"), ROUND_HALF_UP).normalize()
        return f"{n:f} {cap.display_unit}{'' if n == 1 else 's'} ({base})"
    return base


def _expected_lines(batch: RoundedBatch, recipe: RefRecipe, ref: ReferenceData) -> list[tuple[int, Decimal]]:
    """(ingredient id, base quantity) for every recipe line at the batch's scale, in recipe order."""
    out = []
    for line in recipe.lines:
        plan = ref.ingredients[line.ingredient_id]
        scaled = scale_line(
            line.authored_quantity, line.authored_unit, batch.scale_factor, plan.count_rounding_step
        )
        base = to_base(scaled.amount, scaled.unit, plan.units)
        out.append((line.ingredient_id, base.amount.quantize(QTY_TOLERANCE, ROUND_HALF_UP)))
    return out


def _render_check(batch: RoundedBatch, recipe: RefRecipe, ref: ReferenceData) -> list[str]:
    lines = []
    roles = {ln.recipe_ingredient_id: ln.role for ln in recipe.lines}
    for ln in batch.lines:
        plan = ref.ingredients[ln.ingredient_id]
        lines.append(
            LineInput(
                ln.ingredient_id,
                ln.name,
                ln.amount,
                ln.unit,
                grams_of(ln.base_quantity, ln.base_unit, plan.units),
                roles.get(ln.recipe_ingredient_id, "other"),
                ref.safety.get(ln.ingredient_id),
                optional=ln.optional,
            )
        )
    requirement = doneness_requirement(
        [IngredientSafety(ln.name, ln.safety_category, ln.role) for ln in lines if not ln.optional]
    )
    if requirement is None:
        return []
    rendered = render(
        RenderInput(
            recipe.version_id,
            recipe.title,
            recipe.description,
            recipe.is_draft,
            recipe.freezer_friendly,
            batch.portions,
            lines,
            recipe.steps,
            3,
            batch.per_portion,
            ref.daily_values,
        )
    )
    return (
        [] if rendered.safety_notes else [f"{recipe.title}: no safe-temperature line for its doneness check"]
    )


def validate_plan(plan: RoundedPlan, ref: ReferenceData, *, scope: Scope = "week") -> ValidationReport:
    """`scope` "single" (a one-meal plan, Phase 2b): one meal isn't a day, so the day and week calorie limits
    and the protein target are skipped; every other check runs."""
    if not isinstance(plan, RoundedPlan):
        raise TypeError(f"the plan validator only accepts a RoundedPlan, not {type(plan).__name__}")
    c = plan.constraints
    whole_days = scope == "week"
    errors: list[Issue] = []
    warnings: list[Issue] = []
    days = {d.day: d for d in c.days}

    # ---- batches: quantities, scale, schedule, equipment, mood ----
    per_portion_kcal: list[Decimal] = []
    per_portion_protein: list[Decimal] = []
    for index, batch in enumerate(plan.batches):
        recipe = ref.recipes.get(batch.version_id)
        if recipe is None:
            errors.append(
                Issue("UNKNOWN_RECIPE", f"batch {index + 1}: recipe version {batch.version_id} not found")
            )
            per_portion_kcal.append(Decimal(0))
            per_portion_protein.append(Decimal(0))
            continue
        spec = days.get(batch.cook_on)
        if spec is None or not spec.is_cook_day:
            errors.append(
                Issue(
                    "BATCH_ON_NON_COOK_DAY",
                    f"{recipe.title} is cooked on {_day(batch.cook_on)}, not a cook day",
                    day=batch.cook_on,
                )
            )
        elif not mood_allows(spec.mood, recipe.mood):
            errors.append(
                Issue(
                    "MOOD_NOT_ALLOWED",
                    f"{recipe.title} is {recipe.mood.value}; "
                    f"{_day(batch.cook_on)} is a {spec.mood.value} day",
                    day=batch.cook_on,
                )
            )
        if missing := sorted(recipe.equipment - c.equipment):
            errors.append(Issue("EQUIPMENT_UNAVAILABLE", f"{recipe.title} needs {', '.join(missing)}"))
        if batch.portions_to_freeze and not recipe.freezer_friendly:
            errors.append(
                Issue(
                    "FREEZER_NOT_FRIENDLY",
                    f"{recipe.title} doesn't freeze well, so its {batch.portions_to_freeze} extra portions "
                    "can't go in the freezer",
                )
            )
        expected_scale = (
            Decimal(batch.portions)
            * size_multiplier(batch.portion_size)
            * batch.nudge
            * batch.absorption_scale
            / Decimal(recipe.base_servings)
        ).quantize(SCALE_TOLERANCE, ROUND_HALF_UP)
        if abs(expected_scale - batch.scale_factor) > SCALE_TOLERANCE:
            errors.append(
                Issue(
                    "SCALE_MISMATCH", f"{recipe.title}: scale {batch.scale_factor} should be {expected_scale}"
                )
            )
        expected = _expected_lines(batch, recipe, ref)
        for ln, (want_id, want) in zip(batch.lines, expected, strict=False):
            if ln.ingredient_id != want_id:
                errors.append(
                    Issue("QUANTITY_MISMATCH", f"{recipe.title}: {ln.name} is not this line of the recipe")
                )
                continue
            if ln.adjustment == ABSORBED:
                limit = ABSORBED_TOLERANCE.get(ln.base_unit, Decimal(1))
                if abs(ln.base_quantity - want) > max(limit, want * Decimal("0.02")):
                    errors.append(
                        Issue(
                            "QUANTITY_MISMATCH",
                            f"{recipe.title}: {ln.name} {ln.base_quantity} {ln.base_unit} is not the "
                            f"scaled amount ({want})",
                        )
                    )
                continue
            if abs(ln.base_quantity - want) > QTY_TOLERANCE:
                errors.append(
                    Issue(
                        "QUANTITY_MISMATCH",
                        f"{recipe.title}: {ln.name} is {ln.base_quantity} {ln.base_unit}, but practical "
                        f"rounding of the recipe at scale {batch.scale_factor} gives {want} {ln.base_unit}",
                    )
                )
        if len(batch.lines) != len(recipe.lines):
            errors.append(
                Issue(
                    "QUANTITY_MISMATCH",
                    f"{recipe.title}: {len(batch.lines)} lines, recipe has {len(recipe.lines)}",
                )
            )
        counted = [
            (ln.ingredient_id, ln.base_quantity, ln.base_unit) for ln in batch.lines if not ln.optional
        ]
        totals = nutrition_of(counted, ref.ingredients)
        per_portion_kcal.append(totals.amounts.get("energy_kcal", Decimal(0)) / Decimal(batch.portions))
        per_portion_protein.append(totals.amounts.get("protein_g", Decimal(0)) / Decimal(batch.portions))
        for problem_text in _render_check(batch, recipe, ref):
            errors.append(Issue("SAFETY_MISSING", problem_text))
        if recipe.origin == "llm":
            texts = [recipe.title, recipe.description, *(s.text for s in recipe.steps)]
            for text in texts:
                for v in check_text(text):
                    errors.append(Issue("PROSE_FILTER", f"{recipe.title}: {v.message}"))

    # ---- cook-day time, start to finish: each cook day's exact schedule (step 2b.9, V11) ----
    pairs = []
    for batch in plan.batches:
        recipe = ref.recipes.get(batch.version_id)
        if recipe is None:
            continue
        timing = recipe.timing or fallback_timing(recipe.active_minutes, recipe.active_minutes)
        pairs.append(
            (
                batch.cook_on,
                dish_batch(
                    batch.version_id,
                    batch.portion_size.value,
                    title=recipe.title,
                    timing=timing,
                    base_servings=recipe.base_servings,
                    portions=batch.portions,
                ),
            )
        )
    for day, schedule in day_schedules(pairs).items():
        if day in days and schedule.elapsed > days[day].cook_minutes_available:
            have = days[day].cook_minutes_available
            errors.append(
                Issue(
                    "COOK_TIME_OVER",
                    f"{_day(day)} needs about {minutes_text(schedule.elapsed)} start to finish; you have "
                    f"{minutes_text(have)}",
                    day=day,
                    amount=schedule.elapsed - have,
                )
            )

    # ---- meals: slots, fridge window, kcal ----
    filled: dict[tuple[date, MealSlot], int] = defaultdict(int)
    eaten_by_batch: dict[int, int] = defaultdict(int)
    day_kcal: dict[date, int] = {d: 0 for d in days}
    day_protein: dict[date, Decimal] = {d: Decimal(0) for d in days}
    recipe_days: dict[tuple[int, date], int] = defaultdict(int)
    meals_per_recipe: dict[int, int] = defaultdict(int)
    cap_meals: list[tuple[date, Meal]] = []
    for meal in plan.meals:
        filled[(meal.eat_on, meal.slot)] += 1
        if meal.batch_index >= len(plan.batches):
            errors.append(Issue("UNKNOWN_BATCH", f"{_day(meal.eat_on)} {meal.slot.value}: no such batch"))
            continue
        batch = plan.batches[meal.batch_index]
        recipe = ref.recipes.get(batch.version_id)
        eaten_by_batch[meal.batch_index] += 1
        age = (meal.eat_on - batch.cook_on).days
        if age < 0:
            errors.append(
                Issue(
                    "EATEN_BEFORE_COOKED",
                    f"{_day(meal.eat_on)} {meal.slot.value} comes from a batch cooked later",
                    day=meal.eat_on,
                )
            )
        elif age > c.leftover_fridge_days and not (
            meal.from_freezer and recipe is not None and recipe.freezer_friendly
        ):
            errors.append(
                Issue(
                    "FRIDGE_WINDOW",
                    f"{_day(meal.eat_on)} {meal.slot.value}: cooked {age} days earlier, beyond the "
                    f"{c.leftover_fridge_days}-day fridge window, and not frozen",
                    day=meal.eat_on,
                )
            )
        if meal.from_freezer and recipe is not None and not recipe.freezer_friendly:
            errors.append(
                Issue(
                    "FREEZER_NOT_FRIENDLY",
                    f"{_day(meal.eat_on)} {meal.slot.value}: {recipe.title} comes from the freezer, but it "
                    "doesn't freeze well",
                    day=meal.eat_on,
                )
            )
        kcal = kcal_display(per_portion_kcal[meal.batch_index])
        if kcal != meal.kcal:
            errors.append(
                Issue(
                    "KCAL_MISMATCH",
                    f"{_day(meal.eat_on)} {meal.slot.value}: stored {meal.kcal} kcal, recomputed {kcal}",
                    day=meal.eat_on,
                )
            )
        protein = per_portion_protein[meal.batch_index].quantize(_PROTEIN, ROUND_HALF_UP)
        if protein != meal.protein_g:
            errors.append(
                Issue(
                    "PROTEIN_MISMATCH",
                    f"{_day(meal.eat_on)} {meal.slot.value}: stored {meal.protein_g} g protein, "
                    f"recomputed {protein} g",
                    day=meal.eat_on,
                )
            )
        if meal.eat_on in day_kcal:
            day_kcal[meal.eat_on] += kcal
            day_protein[meal.eat_on] += protein
        if recipe is not None:
            recipe_days[(recipe.version_id, meal.eat_on)] += 1
            if meal.slot in VARIETY_CAPPED_SLOTS:
                meals_per_recipe[recipe.version_id] += 1
            cap_meals.append(
                (
                    meal.eat_on,
                    Meal(
                        f"{_day(meal.eat_on)} {meal.slot.value.replace('_', ' ')} ({recipe.title})",
                        frozenset(ln.ingredient_id for ln in recipe.lines),
                    ),
                )
            )
    for spec in c.days:
        for slot in spec.slots:
            n = filled.get((spec.day, slot), 0)
            if n == 0:
                errors.append(
                    Issue("SLOT_MISSING", f"{_day(spec.day)} {slot.value} has no meal", day=spec.day)
                )
            elif n > 1:
                errors.append(
                    Issue("SLOT_DUPLICATE", f"{_day(spec.day)} {slot.value} has {n} meals", day=spec.day)
                )
    for key_day, key_slot in filled:
        if key_day not in days or key_slot not in days[key_day].slots:
            errors.append(Issue("SLOT_NOT_PLANNED", f"{key_day} {key_slot.value} is not a planned slot"))
    people = c.household_size  # a meal is this many portions
    for index, batch in enumerate(plan.batches):
        if eaten_by_batch[index] * people + batch.portions_to_freeze != batch.portions:
            eaten = eaten_by_batch[index] * people
            errors.append(
                Issue(
                    "PORTIONS_MISMATCH",
                    f"{batch.title}: {batch.portions} portions cooked, {eaten} eaten + "
                    f"{batch.portions_to_freeze} frozen",
                )
            )
    for (vid, day), n in recipe_days.items():
        if n > 1:
            errors.append(
                Issue(
                    "RECIPE_TWICE_A_DAY",
                    f"{ref.recipes[vid].title} is eaten {n} times on {_day(day)}",
                    day=day,
                )
            )
    for vid, n in meals_per_recipe.items():
        if n > c.max_portions_per_recipe:
            errors.append(
                Issue(
                    "VARIETY_CAP_EXCEEDED",
                    f"{ref.recipes[vid].title}: {n} meals this week, "
                    f"the limit is {c.max_portions_per_recipe}",
                )
            )

    # ---- calories per mode (from the recomputed, displayed meal values) ----
    tol = c.tolerance
    for spec in c.days if whole_days else ():
        k = day_kcal[spec.day]
        if c.calorie_mode is CalorieMode.STRICT_DAILY:
            ceiling, floor = spec.kcal_target, round(spec.kcal_target * (1 - tol.daily_under_pct / 100))
        else:
            ceiling, floor = spec.kcal_target + tol.daily_band_kcal, spec.kcal_target - tol.daily_band_kcal
        if k > ceiling:
            errors.append(
                Issue(
                    "KCAL_DAY_OVER_CEILING",
                    f"{_day(spec.day)} is {k:,} kcal, {k - ceiling} over the ceiling of {ceiling:,}",
                    day=spec.day,
                    amount=k - ceiling,
                )
            )
        if k < floor:
            errors.append(
                Issue(
                    "KCAL_DAY_UNDER_FLOOR",
                    f"{_day(spec.day)} is {k:,} kcal, {floor - k} under the minimum of {floor:,}",
                    day=spec.day,
                    amount=floor - k,
                )
            )
    week = sum(day_kcal.values())
    if c.calorie_mode is CalorieMode.WEEKLY and whole_days:
        week_floor = round(c.weekly_kcal_target * (1 - tol.weekly_under_pct / 100))
        if week > c.weekly_kcal_target:
            errors.append(
                Issue(
                    "KCAL_WEEK_OVER_CEILING",
                    f"the week is {week:,} kcal, {week - c.weekly_kcal_target} over {c.weekly_kcal_target:,}",
                    amount=week - c.weekly_kcal_target,
                )
            )
        if week < week_floor:
            errors.append(
                Issue(
                    "KCAL_WEEK_UNDER_FLOOR",
                    f"the week is {week:,} kcal, {week_floor - week} under the minimum of {week_floor:,}",
                    amount=week_floor - week,
                )
            )
    if dict(plan.totals.day_kcal) != day_kcal or plan.totals.week_kcal != week:
        errors.append(Issue("TOTALS_MISMATCH", "stored day/week kcal totals don't match the recomputed ones"))

    # ---- protein target per mode (a floor) ----
    target = c.daily_protein_target_g
    if target > 0 and whole_days:
        if c.calorie_mode is CalorieMode.STRICT_DAILY:
            for spec in c.days:
                short = Decimal(target) - day_protein[spec.day]
                if short > 0:
                    errors.append(
                        Issue(
                            "PROTEIN_DAY_UNDER_TARGET",
                            f"{_day(spec.day)} has {day_protein[spec.day]} g protein, {short} g under your "
                            f"target of {target} g",
                            day=spec.day,
                            amount=int(short.to_integral_value(ROUND_HALF_UP)) or 1,
                        )
                    )
        else:
            total = sum(day_protein.values(), Decimal(0))
            short = Decimal(c.week_protein_target_g) - total
            if short > 0:
                errors.append(
                    Issue(
                        "PROTEIN_WEEK_UNDER_TARGET",
                        f"the week has {total} g protein, {short} g under your target of "
                        f"{c.week_protein_target_g:,} g ({target} g a day)",
                        amount=int(short.to_integral_value(ROUND_HALF_UP)) or 1,
                    )
                )
    if dict(plan.totals.day_protein_g) != day_protein:
        errors.append(Issue("TOTALS_MISMATCH", "stored day protein totals don't match the recomputed ones"))

    # ---- diet rules on the final meals ----
    for batch in plan.batches:
        for ln in batch.lines:
            if (
                ln.ingredient_id in ref.excluded_ingredient_ids
                or ln.ingredient_id in c.excluded_ingredient_ids
            ):
                errors.append(
                    Issue("EXCLUDED_INGREDIENT", f"{batch.title} uses {ln.name}, which is excluded or held")
                )
    caps = [
        DomainCap(cap.label, cap.member_ingredient_ids, cap.max_meals_per_week, cap.never_favor)
        for cap in ref.caps
    ]
    week_use = {(u.week_start, u.label): u.used for u in c.cap_week_use}
    for violation in weekly_cap_violations(caps, cap_meals, week_use):
        errors.append(
            Issue("FREQUENCY_CAP_EXCEEDED", violation.message, details={"meals": list(violation.meals)})
        )

    # ---- daily amount caps (M16): every meal that day, your portion, from the rounded lines ----
    for dcap in c.daily_amount_caps:
        plan_ = ref.ingredients.get(dcap.ingredient_id)
        if plan_ is None:
            continue
        per_portion: dict[int, Decimal] = {}
        for index, batch in enumerate(plan.batches):
            total = sum(
                (
                    convert(ln.base_quantity, ln.base_unit, dcap.unit, plan_.units)
                    for ln in batch.lines
                    if ln.ingredient_id == dcap.ingredient_id and not ln.optional
                ),
                Decimal(0),
            )
            if total > 0:
                per_portion[index] = total / Decimal(batch.portions)
        day_amount: dict[date, Decimal] = defaultdict(Decimal)
        for meal in plan.meals:
            day_amount[meal.eat_on] += per_portion.get(meal.batch_index, Decimal(0))
        for day, amount in sorted(day_amount.items()):
            excess = amount - dcap.maximum
            if excess > AMOUNT_TOLERANCE:
                errors.append(
                    Issue(
                        "DAILY_AMOUNT_OVER",
                        f"{_day(day)} has {_cap_amount(amount, dcap)} of {dcap.label.lower()}, over your "
                        f"daily maximum of {_cap_amount(dcap.maximum, dcap)}",
                        day=day,
                        amount=int(excess.to_integral_value(ROUND_HALF_UP)) or 1,
                        details={"ingredient_id": dcap.ingredient_id, "over": str(excess)},
                    )
                )

    # ---- groceries: coverage, inventory, budget ----
    grocery = build_grocery(c, plan.batches, ref.ingredients)
    available = {i: plan_.available for i, plan_ in ref.ingredients.items()}
    for item in plan.grocery.items:
        if item.kind == "always_have":  # unlimited stock you own
            continue
        if item.inventory_used > available.get(item.ingredient_id, Decimal(0)) + QTY_TOLERANCE:
            errors.append(
                Issue(
                    "INVENTORY_OVERUSE",
                    f"{item.name}: uses {item.inventory_used} {item.unit} from inventory; "
                    f"you have {available.get(item.ingredient_id, 0)}",
                )
            )
    bought: dict[int, Decimal] = defaultdict(Decimal)
    for item in plan.grocery.items:
        bought[item.ingredient_id] += item.bought or Decimal(0)
    for item in plan.grocery.items:
        if item.kind in ("buy", "from_inventory"):
            covered = item.inventory_used + bought[item.ingredient_id]
            tolerance = Decimal(1) if item.unit != "count" else Decimal(0)
            if covered + tolerance < item.needed:
                errors.append(
                    Issue(
                        "INGREDIENT_NOT_COVERED",
                        f"{item.name}: need {item.needed} {item.unit}, have {item.inventory_used} + "
                        f"buying {bought[item.ingredient_id]}",
                    )
                )
    if c.allowed_purchase_ingredient_ids is not None:  # "Use what I have": only your could-buy items
        for item in plan.grocery.items:
            buys = (item.kind == "buy" and (item.bought or item.to_buy) > 0) or item.kind == "unpriced"
            if buys and not c.may_buy(item.ingredient_id):
                errors.append(
                    Issue(
                        "PURCHASE_NOT_ALLOWED",
                        f"{item.name} isn't one of your could-buy items, but the plan would buy "
                        f"{_qty(item.to_buy, item.unit)}",
                        details={"ingredient_id": item.ingredient_id},
                    )
                )
    if grocery.total_cents != plan.grocery.total_cents or plan.totals.cost_cents != grocery.total_cents:
        errors.append(
            Issue(
                "TOTALS_MISMATCH",
                f"stored grocery total {plan.grocery.total_cents}¢, recomputed {grocery.total_cents}¢",
            )
        )
    if not grocery.complete:
        warnings.append(
            Issue(
                "COST_INCOMPLETE",
                f"cost incomplete: no price yet for {', '.join(grocery.unpriced)}",
                details={"unpriced": list(grocery.unpriced)},
            )
        )
        limited_unpriced = [
            item.name for item in grocery.items if item.kind == "unpriced" and c.limit_covers(item.stock_up)
        ]
        if limited_unpriced:
            errors.append(
                Issue(
                    "UNPRICED_WITH_PURCHASE_LIMIT",
                    f"a purchase limit can't be checked without prices for {', '.join(limited_unpriced)}",
                )
            )
    purchase_limit = c.purchase_limit_cents
    if c.planning_mode is PlanningMode.INVENTORY:
        limited, what = grocery.total_cents, "top-up"
    else:
        limited, what = grocery.regular_cents, "budget for regular groceries"
    if purchase_limit is not None and limited > purchase_limit:
        over = limited - purchase_limit
        errors.append(
            Issue(
                "PURCHASE_LIMIT_OVER",
                f"this trip costs {_money(limited)}, {_money(over)} over your "
                f"{_money(purchase_limit)} {what}",
                amount=over,
            )
        )

    # ---- money and perishables, recomputed ----
    costs, leftovers = cost_summary(c, plan.batches, grocery, ref.ingredients, plan.meals)
    if costs != plan.costs or leftovers != plan.leftovers:
        errors.append(Issue("TOTALS_MISMATCH", "stored costs or leftovers don't match the recomputed ones"))
    freeze = freeze_instructions(c, plan.batches, grocery, ref.ingredients)
    if missing_freeze := [f for f in freeze if f not in plan.freeze]:
        names = ", ".join(sorted({f.name for f in missing_freeze}))
        errors.append(
            Issue("SAFETY_MISSING", f"raw protein needs a freeze-on-shopping-day instruction: {names}")
        )
    for left in leftovers:
        if left.fate == "at_risk":
            warnings.append(
                Issue(
                    "EXPECTED_WASTE",
                    f"{left.name}: about {_qty(left.quantity, left.unit)} left with no use planned; "
                    f"likely to spoil ({_money(left.cents)})",
                    amount=left.cents,
                )
            )
    used_lots = {lot_id for lot_id, _ in grocery.inventory_takes}
    for plan_ in ref.ingredients.values():
        if plan_.always_have:  # plans don't track Always-have lots
            continue
        for lot in plan_.lots:
            if lot.expires_on is not None and lot.expires_on <= c.week_end and lot.id not in used_lots:
                warnings.append(
                    Issue(
                        "EXPIRING_UNUSED",
                        f"{plan_.name} in your inventory expires {_day(lot.expires_on)} and isn't used",
                    )
                )
    return ValidationReport(tuple(errors), tuple(warnings), day_kcal, week, grocery.total_cents)
