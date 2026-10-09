"""Practical rounding of one solved batch (§7.1): every line scaled from its authored quantity, rounded to
something you can measure, and the batch's per-portion nutrition recomputed from the rounded amounts."""

from decimal import ROUND_HALF_UP, Decimal

from app.domain.scaling import MAX_SCALE_FACTOR, ScalingError, scale_line
from app.domain.units import convert, to_base
from app.planning.problem import PlanningProblem, size_multiplier
from app.planning.recipe_math import nutrition_of
from app.planning.rounded import ABSORBED, RoundedBatch, RoundedLine
from app.planning.solver.model import SolvedBatch

_Q3 = Decimal("0.001")
_Q4 = Decimal("0.0001")
_PROTEIN = Decimal("0.1")


def q3(value: Decimal) -> Decimal:
    return value.quantize(_Q3, rounding=ROUND_HALF_UP)


def batch_scale(portions: int, size_and_nudge: Decimal, absorption: Decimal, base_servings: int) -> Decimal:
    factor = (Decimal(portions) * size_and_nudge * absorption / Decimal(base_servings)).quantize(
        _Q4, ROUND_HALF_UP
    )
    if factor <= 0 or factor > MAX_SCALE_FACTOR:
        raise ScalingError(f"scale factor {factor} is outside (0, {MAX_SCALE_FACTOR}]")
    return factor


def round_batch(
    problem: PlanningProblem,
    solved: SolvedBatch,
    *,
    absorption: Decimal = Decimal(1),
    absorbed: tuple[int, Decimal] | None = None,  # (ingredient id, exact base quantity to use)
) -> RoundedBatch:
    recipe = problem.candidate(solved.version_id)
    factor = batch_scale(
        solved.portions, size_multiplier(solved.portion_size) * solved.nudge, absorption, recipe.base_servings
    )
    lines: list[RoundedLine] = []
    absorbed_done = False
    for line in recipe.lines:
        plan = problem.ingredients[line.ingredient_id]
        if (
            absorbed is not None
            and line.ingredient_id == absorbed[0]
            and not line.optional
            and not absorbed_done
        ):
            base_qty = absorbed[1]
            unit = line.unit
            amount = (
                convert(base_qty, unit, line.authored_unit, plan.units)
                if line.authored_unit != unit
                else base_qty
            )
            lines.append(
                RoundedLine(
                    line.recipe_ingredient_id,
                    line.ingredient_id,
                    plan.name,
                    q3(amount),
                    line.authored_unit,
                    q3(base_qty),
                    unit,
                    line.optional,
                    ABSORBED,
                )
            )
            absorbed_done = True
            continue
        scaled = scale_line(line.authored_quantity, line.authored_unit, factor, plan.count_rounding_step)
        base = to_base(scaled.amount, scaled.unit, plan.units)
        lines.append(
            RoundedLine(
                line.recipe_ingredient_id,
                line.ingredient_id,
                plan.name,
                scaled.amount,
                scaled.unit,
                q3(base.amount),
                base.unit.value,
                line.optional,
            )
        )
    counted = [(ln.ingredient_id, ln.base_quantity, ln.base_unit) for ln in lines if not ln.optional]
    totals = nutrition_of(counted, problem.ingredients)
    per_portion = {code: value / Decimal(solved.portions) for code, value in totals.amounts.items()}
    return RoundedBatch(
        version_id=solved.version_id,
        title=recipe.title,
        cook_on=solved.cook_on,
        portions=solved.portions,
        portions_to_freeze=solved.portions_to_freeze,
        portion_size=solved.portion_size,
        nudge=solved.nudge,
        absorption_scale=absorption,
        scale_factor=factor,
        planned_minutes=recipe.active_minutes,
        lines=tuple(lines),
        per_portion=per_portion,
        absorbed_ingredient_id=absorbed[0] if absorbed is not None else None,
    )
