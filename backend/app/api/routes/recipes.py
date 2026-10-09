from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.presenters import costs_out, nutrition_out
from app.domain.enums import PortionSize, RecipeOrigin
from app.schemas.api import SeedRecipeOut
from app.schemas.recipes import (
    RecipeOut,
    RecipeVersionOut,
    RecipeVersionSummaryOut,
    RenderedLineOut,
    RenderedStepOut,
)
from app.services.recipes import VersionView, recipe_view, seed_recipes, version_view

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])
versions_router = APIRouter(prefix="/api/v1/recipe-versions", tags=["recipes"])


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


def version_out(session: DbSession, view: VersionView) -> RecipeVersionOut:
    v, r, rendered, calc = view.version, view.recipe, view.rendered, view.calculation
    return RecipeVersionOut(
        version_id=v.id,
        recipe_id=r.id,
        version_number=v.version_number,
        title=v.title,
        description=v.description,
        badge=rendered.badge,
        origin=r.origin,
        meal_slots=list(v.meal_slots),
        mood=v.mood,
        cuisine=v.cuisine,
        flavor_tags=list(v.flavor_tags),
        equipment=list(v.equipment),
        freezer_friendly=v.freezer_friendly,
        base_servings=v.base_servings,
        portions=view.portions,
        portion_size=view.portion_size.value,
        active_minutes=v.active_minutes,
        total_minutes=v.total_minutes,
        time_note="est." if r.origin == RecipeOrigin.LLM.value else "",
        lines=[
            RenderedLineOut(
                ingredient_id=ln.ingredient_id,
                name=ln.name,
                display=ln.display,
                preparation=ln.preparation,
                optional=ln.optional,
            )
            for ln in rendered.lines
        ],
        steps=[
            RenderedStepOut(
                section=s.section,
                text=s.text,
                duration_minutes=s.duration_minutes,
                appliance_temp_f=s.appliance_temp_f,
                safety_note=s.safety_note,
                added_by_app=s.added_by_app,
            )
            for s in rendered.steps
        ],
        per_container=rendered.per_container,
        labels=list(rendered.labels),
        heme_note=rendered.heme_note,
        per_portion=nutrition_out(session, calc.per_portion, with_labels=True),
        costs=costs_out(calc.costs),
        incomplete_reasons=list(calc.incomplete_reasons),
        change_summary=v.change_summary,
        created_at=v.created_at,
    )


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, session: DbSession, user: CurrentUser) -> RecipeOut:
    view = recipe_view(session, user.id, recipe_id)
    return RecipeOut(
        recipe_id=view.recipe.id,
        title=view.recipe.title,
        origin=view.recipe.origin,
        family=view.family,
        default_version_id=view.recipe.default_version_id,
        versions=[
            RecipeVersionSummaryOut(
                version_id=v.id,
                version_number=v.version_number,
                created_by=v.created_by,
                is_draft=v.is_draft,
                change_summary=v.change_summary,
                created_at=v.created_at,
            )
            for v in view.versions
        ],
        default_version=version_out(session, view.default) if view.default else None,
    )


@versions_router.get("/{version_id}", response_model=RecipeVersionOut)
def get_version(
    version_id: int,
    session: DbSession,
    user: CurrentUser,
    portions: Annotated[int | None, Query(ge=1, le=40)] = None,
    portion_size: Annotated[PortionSize | None, Query()] = None,
) -> RecipeVersionOut:
    """A recipe version scaled to any number of portions: practical quantities, code-computed nutrition
    and cost, and the food-safety lines the app injects."""
    return version_out(session, version_view(session, user.id, version_id, portions, portion_size))
