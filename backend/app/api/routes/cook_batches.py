from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.presenters import inventory_lots_out
from app.api.routes.recipes import version_out
from app.domain.enums import MealSlot
from app.planning.rounded import meal_key
from app.schemas.plans import BatchDetailOut, BatchLineOut, CookedIn, CookedOut, DeductionOut, MealOut
from app.services import cooking as service
from app.services.dishes import dish_categories
from app.services.plans import amount_display, batch_nutrition, money

router = APIRouter(prefix="/api/v1/cook-batches", tags=["cooking"])


@router.get("/{batch_id}", response_model=BatchDetailOut)
def get_batch(batch_id: int, session: DbSession, user: CurrentUser) -> BatchDetailOut:
    """A cook batch's recipe at its practical quantities, with the plan's package and freezing notes."""
    view = service.batch_view(session, user.id, batch_id)
    b, v = view.batch, view.version
    protein = batch_nutrition(session, [b.id]).get(b.id, {}).get("protein_g")
    category = dish_categories(session, [v.version.id])[v.version.id].value
    meal_cents: dict[str, int] = view.plan.totals.get("costs", {}).get("meal_cents", {})
    return BatchDetailOut(
        id=b.id,
        plan_id=view.plan.id,
        status=b.status,
        cook_on=b.cook_on,
        portions=b.portions,
        portions_to_freeze=b.portions_to_freeze,
        portion_size=b.portion_size,
        planned_minutes=b.planned_minutes,
        meals=[
            MealOut(
                eat_on=m.eat_on,
                slot=MealSlot(m.slot),
                recipe_version_id=v.version.id,
                recipe_id=v.recipe.id,
                title=v.version.title,
                is_draft=v.version.is_draft,
                kcal=m.planned_kcal,
                protein_g=(protein or Decimal(0)).quantize(Decimal("0.1"), ROUND_HALF_UP),
                from_freezer=m.from_freezer,
                cook_batch_id=b.id,
                note="From the freezer: move it to the fridge the night before." if m.from_freezer else None,
                dish_category=category,
                cost_cents=(cents := meal_cents.get(meal_key(m.eat_on, m.slot))),
                cost_display=money(cents) if cents is not None else None,
            )
            for m in view.meals
        ],
        lines=[
            BatchLineOut(
                ingredient_id=row.ingredient_id,
                name=name,
                display=display,
                preparation=prep,
                optional=optional,
                adjustment=row.adjustment,
            )
            for row, name, display, prep, optional in view.lines
        ],
        package_notes=view.package_notes,
        freeze_notes=view.freeze_notes,
        recipe=version_out(session, v),
    )


@router.post("/{batch_id}/cooked", response_model=CookedOut)
def mark_cooked(batch_id: int, body: CookedIn, session: DbSession, user: CurrentUser) -> CookedOut:
    """Mark a batch cooked: its practical quantities come out of inventory (open packages first) and a package
    it opens stays as an open-package lot. Cooking the same batch twice is a 409."""
    result = service.mark_cooked(session, user.id, batch_id, body.cooked_on)
    session.commit()
    return CookedOut(
        batch_id=result.batch.id,
        status=result.batch.status,
        title=result.title,
        deductions=[
            DeductionOut(
                ingredient_id=d.ingredient_id,
                name=d.name,
                needed=amount_display(d.needed, d.unit),
                taken=amount_display(d.taken, d.unit),
                shortfall=amount_display(d.shortfall, d.unit) if d.shortfall > 0 else None,
            )
            for d in result.deductions
        ],
        open_packages=inventory_lots_out(session, result.opened),
    )
