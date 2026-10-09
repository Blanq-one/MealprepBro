from decimal import Decimal

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.presenters import costs_out, line_out, nutrition_out
from app.domain.scaling import PORTION_MULTIPLIERS
from app.schemas.api import RecipeCalculationIn, RecipeCalculationOut
from app.services.calculations import LineInput, calculate, calculate_scaled

router = APIRouter(prefix="/api/v1/calculations", tags=["calculations"])


@router.post("/recipe", response_model=RecipeCalculationOut)
def calculate_recipe(body: RecipeCalculationIn, session: DbSession) -> RecipeCalculationOut:
    """Nutrition and per-store cost for a list of lines. With `scale_to_portions`, every line is first
    scaled and rounded to a practical amount, and the numbers are computed from the rounded amounts."""
    lines = [
        LineInput(line.ingredient_id, Decimal(line.quantity), line.unit, line.optional) for line in body.lines
    ]
    if body.scale_to_portions is None:
        calc = calculate(session, lines, body.servings)
        factor = Decimal(1)
    else:
        scaled = calculate_scaled(
            session,
            lines,
            body.servings,
            body.scale_to_portions,
            PORTION_MULTIPLIERS[body.portion_size.value],
        )
        calc, factor = scaled.calculation, scaled.factor
    return RecipeCalculationOut(
        portions=calc.portions,
        scale_factor=factor.quantize(Decimal("0.0001")),
        lines=[line_out(r) for r in calc.lines],
        total=nutrition_out(session, calc.totals, with_labels=False),
        per_portion=nutrition_out(session, calc.per_portion, with_labels=True),
        costs=costs_out(calc.costs),
        optional_not_counted=list(calc.optional_not_counted),
        nutrition_complete=calc.nutrition_complete,
        incomplete_reasons=list(calc.incomplete_reasons),
    )
