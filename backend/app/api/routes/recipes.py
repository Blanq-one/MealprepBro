from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession, LLMClientFactory, LLMClock, LLMSettings, SessionFactory
from app.api.presenters import costs_out, nutrition_out
from app.cook import search as search_service
from app.cook.saved import saved_cards
from app.cook.stream import steps_events
from app.domain.enums import PortionSize, RecipeOrigin
from app.schemas.api import SeedRecipeOut
from app.schemas.cards import SearchContextOut
from app.schemas.cook import StepsStreamEvent
from app.schemas.recipes import (
    RecipeOut,
    RecipeVersionOut,
    RecipeVersionSummaryOut,
    RenderedLineOut,
    RenderedStepOut,
    SavedRecipeOut,
)
from app.services import favorites
from app.services.dishes import dish_categories
from app.services.recipes import VersionView, recipe_view, seed_recipes, version_view

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])
versions_router = APIRouter(prefix="/api/v1/recipe-versions", tags=["recipes"])
NDJSON = "application/x-ndjson"


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


def version_out(
    session: DbSession, view: VersionView, search_context: SearchContextOut | None = None
) -> RecipeVersionOut:
    v, r, rendered, calc = view.version, view.recipe, view.rendered, view.calculation
    marks = favorites.marks(session, r.user_id, [r.id])
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
                amount_display=ln.amount_display,
                portion_note=ln.portion_note,
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
        ]
        if v.steps_status is None  # a new idea shows no steps (not even the app's lines) until written
        else [],
        per_container=rendered.per_container,
        labels=list(rendered.labels),
        heme_note=rendered.heme_note,
        per_portion=nutrition_out(session, calc.per_portion, with_labels=True),
        costs=costs_out(calc.costs),
        incomplete_reasons=list(calc.incomplete_reasons),
        change_summary=v.change_summary,
        created_at=v.created_at,
        dish_category=dish_categories(session, [v.id])[v.id].value,
        is_favorite=r.id in marks.favorites,
        is_saved=r.id in marks.saved,
        steps_ready=v.steps_status is None,
        search_context=search_context,
    )


@router.get("/saved", response_model=list[SavedRecipeOut])
def list_saved(
    session: DbSession,
    user: CurrentUser,
    list_: Annotated[favorites.SavedList, Query(alias="list")] = favorites.SavedList.FAVORITES,
) -> list[SavedRecipeOut]:
    """Your ♥ favorites or 🔖 saved-for-later recipes as cards, most recently saved first, at your household's
    portions, with pantry coverage against your current pantry."""
    return saved_cards(session, user, list_, search_service.local_now(user))


def _mark(session: DbSession, user_id: int, recipe_id: int, which: favorites.SavedList, on: bool) -> Response:
    favorites.set_mark(session, user_id, recipe_id, which, on)
    session.commit()
    return Response(status_code=204)


@router.put("/{recipe_id}/favorite", status_code=204)
def add_favorite(recipe_id: int, session: DbSession, user: CurrentUser) -> Response:
    """♥ on: suggest this more often (a boost in rankings and plans whenever it fits). Idempotent."""
    return _mark(session, user.id, recipe_id, favorites.SavedList.FAVORITES, True)


@router.delete("/{recipe_id}/favorite", status_code=204)
def remove_favorite(recipe_id: int, session: DbSession, user: CurrentUser) -> Response:
    return _mark(session, user.id, recipe_id, favorites.SavedList.FAVORITES, False)


@router.put("/{recipe_id}/saved", status_code=204)
def add_saved(recipe_id: int, session: DbSession, user: CurrentUser) -> Response:
    """🔖 on: save for later, a plain bookmark with no effect on ranking. Idempotent."""
    return _mark(session, user.id, recipe_id, favorites.SavedList.LATER, True)


@router.delete("/{recipe_id}/saved", status_code=204)
def remove_saved(recipe_id: int, session: DbSession, user: CurrentUser) -> Response:
    return _mark(session, user.id, recipe_id, favorites.SavedList.LATER, False)


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


def page_payload(
    session: Session,
    user_id: int,
    version_id: int,
    *,
    portions: int | None,
    portion_size: PortionSize | None,
    search: int | None,
) -> RecipeVersionOut:
    if search is not None and portions is None:  # open at the search card's portions (C8)
        card = search_service.card_portions(session, user_id, search, version_id)
        if card is not None:
            portions, portion_size = card[0], portion_size or card[1]
    view = version_view(session, user_id, version_id, portions, portion_size)
    context = None
    if search is not None:
        counted = [
            (ln.ingredient.id, ln.quantity, ln.unit) for ln in view.calculation.lines if not ln.optional
        ]
        context = search_service.search_context(session, user_id, search, version_id, counted)
    return version_out(session, view, context)


Portions = Annotated[int | None, Query(ge=1, le=40)]
Size = Annotated[PortionSize | None, Query()]
SearchId = Annotated[int | None, Query(description="a meal-now search: its coverage lines for this recipe")]


@versions_router.get("/{version_id}", response_model=RecipeVersionOut)
def get_version(
    version_id: int,
    *,
    session: DbSession,
    user: CurrentUser,
    portions: Portions = None,
    portion_size: Size = None,
    search: SearchId = None,
) -> RecipeVersionOut:
    """A recipe version scaled to any number of portions: practical quantities, code-computed nutrition
    and cost, and the food-safety lines the app injects. With `search`, that search's pantry coverage and
    substitute lines for this recipe (the numbers stay those of the recipe as written). A new idea's steps
    are empty until written (`steps_ready` false; POST .../steps writes them)."""
    return page_payload(
        session, user.id, version_id, portions=portions, portion_size=portion_size, search=search
    )


@versions_router.post(
    "/{version_id}/steps",
    response_class=StreamingResponse,
    responses={
        200: {"model": StepsStreamEvent, "content": {NDJSON: {}}, "description": "NDJSON event lines"}
    },
)
def write_steps(
    version_id: int,
    *,
    session: DbSession,
    user: CurrentUser,
    session_factory: SessionFactory,
    client_factory: LLMClientFactory,
    clock: LLMClock,
    llm_settings: LLMSettings,
    portions: Portions = None,
    portion_size: Size = None,
    search: SearchId = None,
) -> StreamingResponse:
    """E19: writes a new idea's steps the first time it is opened and saves them with the recipe (once).
    Returns at once when they exist; a second request for the same recipe waits for the call already running.
    The result carries the recipe page payload (same query as GET), or `waiting` with `retry_after_s`."""
    version_view(session, user.id, version_id)  # 404 before the stream starts

    def present(worker_session: Session) -> dict[str, Any]:
        out = page_payload(
            worker_session, user.id, version_id, portions=portions, portion_size=portion_size, search=search
        )
        return out.model_dump(mode="json")

    events = steps_events(
        session_factory,
        user.id,
        version_id,
        client_factory=client_factory,
        present=present,
        clock=clock,
        settings=llm_settings,
    )
    return StreamingResponse(
        events, media_type=NDJSON, headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    )
