"""Not for me (step 2b.7, F24; storage approved Z5): a recipe you hide leaves every future suggestion and
plan (meal-now results, meal prep, swaps from 2b.6), until you show it again from Settings, Hidden recipes.
Plans already made keep it (Swap replaces one meal). Dishes, prep items and assemblies are all recipes, so
each can be hidden; from 2b.11, a hidden prep item also leaves out the assemblies that use it (F32).

Like ♥ and 🔖 (services/favorites.py): idempotent, and each real change writes exactly one append-only
feedback_event, recipe_hidden or recipe_unhidden, with the plan meal you tapped it on."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import FeedbackEvent, MealPlan, PlanMeal, Recipe, RecipeHidden, RecipeVersion
from app.schemas.feedback import HIDDEN_PAYLOAD_VERSION, FeedbackEventType, HiddenPayload
from app.services.favorites import _recipe
from app.services.recipes import RecipeNotFoundError


def _plan_meal(session: Session, user_id: int, plan_meal_id: int | None) -> int | None:
    if plan_meal_id is None:
        return None
    meal = session.get(PlanMeal, plan_meal_id)
    plan = session.get(MealPlan, meal.meal_plan_id) if meal is not None else None
    if meal is None or plan is None or plan.user_id != user_id:
        raise RecipeNotFoundError(f"plan meal {plan_meal_id} not found")
    return meal.id


def set_hidden(
    session: Session, user_id: int, recipe_id: int, hidden: bool, *, plan_meal_id: int | None = None
) -> bool:
    """Hide a recipe (Not for me) or show it again. Returns whether anything changed; a repeat logs
    nothing."""
    recipe = _recipe(session, user_id, recipe_id)
    meal_id = _plan_meal(session, user_id, plan_meal_id)
    if hidden:
        changed = session.execute(
            insert(RecipeHidden)
            .values(user_id=user_id, recipe_id=recipe_id)
            .on_conflict_do_nothing()
            .returning(RecipeHidden.recipe_id)
        ).first()
    else:
        changed = session.execute(
            delete(RecipeHidden)
            .where(RecipeHidden.user_id == user_id, RecipeHidden.recipe_id == recipe_id)
            .returning(RecipeHidden.recipe_id)
        ).first()
    if changed is None:
        return False
    version = session.get(RecipeVersion, recipe.default_version_id) if recipe.default_version_id else None
    session.add(
        FeedbackEvent(
            user_id=user_id,
            event_type=(
                FeedbackEventType.RECIPE_HIDDEN if hidden else FeedbackEventType.RECIPE_UNHIDDEN
            ).value,
            occurred_at=datetime.now(UTC),
            recipe_id=recipe.id,
            recipe_version_id=recipe.default_version_id,
            plan_meal_id=meal_id,
            payload=HiddenPayload(kind=version.kind if version is not None else "dish").model_dump(
                mode="json"
            ),
            payload_version=HIDDEN_PAYLOAD_VERSION,
        )
    )
    session.flush()
    return True


def hidden_recipe_ids(session: Session, user_id: int) -> frozenset[int]:
    """The recipes you hid: the planner and meal now leave them out."""
    return frozenset(session.scalars(select(RecipeHidden.recipe_id).where(RecipeHidden.user_id == user_id)))


@dataclass(frozen=True)
class HiddenRow:
    recipe: Recipe
    version: RecipeVersion
    hidden_at: datetime


def hidden_rows(session: Session, user_id: int) -> list[HiddenRow]:
    """Settings, Hidden recipes: every hidden recipe at its default version, most recently hidden first."""
    rows = session.execute(
        select(RecipeHidden, Recipe, RecipeVersion)
        .join(Recipe, Recipe.id == RecipeHidden.recipe_id)
        .join(RecipeVersion, RecipeVersion.id == Recipe.default_version_id)
        .where(RecipeHidden.user_id == user_id, Recipe.archived_at.is_(None))
        .order_by(RecipeHidden.created_at.desc(), RecipeHidden.recipe_id)
    ).tuples()
    return [HiddenRow(recipe, version, hidden.created_at) for hidden, recipe, version in rows]
