from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.presenters import costs_out, nutrition_out
from app.schemas.api import SeedRecipeOut
from app.services.recipes import seed_recipes

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])


@router.get("/seed", response_model=list[SeedRecipeOut])
def list_seed_recipes(session: DbSession, user: CurrentUser) -> list[SeedRecipeOut]:
    """The draft seed library with nutrition and cost per serving, or the reasons it's incomplete."""
    out = []
    for view in seed_recipes(session, user.id):
        calc = view.calculation
        out.append(
            SeedRecipeOut(
                recipe_id=view.recipe.id,
                version_id=view.version.id,
                family=view.family,
                title=view.version.title,
                is_draft=view.version.is_draft,
                draft_note=view.version.change_summary,
                meal_slots=list(view.version.meal_slots),
                mood=view.version.mood,
                base_servings=view.version.base_servings,
                active_minutes=view.version.active_minutes,
                total_minutes=view.version.total_minutes,
                equipment=list(view.version.equipment),
                status="complete" if calc.nutrition_complete else "incomplete",
                incomplete_reasons=list(calc.incomplete_reasons),
                per_serving=nutrition_out(session, calc.per_portion, with_labels=True),
                costs=costs_out(calc.costs),
            )
        )
    return out
