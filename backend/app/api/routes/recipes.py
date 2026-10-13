from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession, LLMClientFactory, LLMClock, LLMSettings, SessionFactory
from app.api.presenters import costs_out, nutrition_out
from app.api.problems import ProblemError
from app.cook import search as search_service
from app.cook.saved import saved_cards
from app.cook.stream import steps_events
from app.domain.assembly_text import portions_text
from app.domain.enums import PortionSize, RecipeKind, RecipeOrigin
from app.domain.prep_storage import PrepStorage
from app.planning.assemblies import Assembly, ItemPortion
from app.schemas.api import SeedRecipeOut
from app.schemas.cards import SearchContextOut
from app.schemas.cook import StepsStreamEvent
from app.schemas.plans import AddToListOut
from app.schemas.recipes import (
    AssemblyItemOut,
    AssemblyOut,
    BudgetPairOut,
    HiddenRecipeOut,
    LeaveOutOut,
    LineOptionsOut,
    PrepItemOut,
    PrepStageOut,
    RecipeEditIn,
    RecipeEditOut,
    RecipeOut,
    RecipeVersionOut,
    RecipeVersionSummaryOut,
    RenderedLineOut,
    RenderedStepOut,
    SavedRecipeOut,
    ShoppingTargetOut,
    StorageOut,
    SwapChoiceOut,
)
from app.services import favorites, hidden
from app.services import plans as plan_service
from app.services import recipe_edits as edits
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
                kind=view.version.kind,
            )
        )
    return out


STATE_DISPLAY = {"raw": "Raw", "marinated": "Marinated", "partly_cooked": "Partly cooked", "cooked": "Cooked"}


def storage_out(storage: PrepStorage) -> StorageOut:
    return StorageOut(
        stored=storage.stored,
        made_on_the_day=storage.made_on_the_day,
        fridge_days=storage.fridge_days,
        freezer=storage.freezer,
        note=storage.note,
        sources=[f"{s.citation}: {s.food} ({s.refrigerator}; {s.freezer})" for s in storage.sources],
    )


def prep_out(item: ItemPortion, pairs_with: list[str]) -> PrepItemOut:
    return PrepItemOut(
        label=item.label,
        brings=item.brings.value,
        pairs_with=pairs_with,
        stages=[
            PrepStageOut(
                n=n,
                state=state.value,
                state_display=STATE_DISPLAY[state.value],
                storage=storage_out(storage),
            )
            for n, (state, storage) in enumerate(zip(item.states, item.storage, strict=True), start=1)
        ],
    )


def assembly_out(assembly: Assembly) -> AssemblyOut:
    items = []
    for part in assembly.parts:
        per = part.item.per_portion.amounts
        kcal = part.portions * per.get("energy_kcal", Decimal(0))
        protein = part.portions * per.get("protein_g", Decimal(0))
        items.append(
            AssemblyItemOut(
                recipe_id=part.item.recipe_id,
                version_id=part.item.version_id,
                kind=part.item.kind.value,
                title=part.item.title,
                label=part.item.label,
                brings=part.item.brings.value,
                portions=part.portions,
                portions_display=portions_text(part.portions),
                min_portions=part.min_portions,
                max_portions=part.max_portions,
                step=part.step,
                kcal=int(kcal.quantize(Decimal(1), ROUND_HALF_UP)),
                protein_g=protein.quantize(Decimal("0.1"), ROUND_HALF_UP),
            )
        )
    return AssemblyOut(name=assembly.name, items=items, instruction=assembly.instruction)


def version_out(
    session: DbSession, view: VersionView, search_context: SearchContextOut | None = None
) -> RecipeVersionOut:
    v, r, rendered, calc = view.version, view.recipe, view.rendered, view.calculation
    marks = favorites.marks(session, r.user_id, [r.id])
    is_hidden = r.id in hidden.hidden_recipe_ids(session, r.user_id)
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
        freeze_note=v.freeze_note,
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
                line_id=ln.line_id,
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
                stage=s.stage,
                flag=s.flag,
            )
            for s in rendered.steps
        ]
        # a new idea shows no steps (not even the app's lines) until written; an assembly has none, only its
        # instruction (step 2b.10)
        if v.steps_status is None and v.kind != RecipeKind.ASSEMBLY.value
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
        kind=v.kind,
        prep=prep_out(view.item, list(v.pairs_with or [])) if view.item is not None else None,
        assembly=assembly_out(view.assembly) if view.assembly is not None else None,
        is_hidden=is_hidden,
        your_version=v.created_by == "user",
        parent_version_id=v.parent_version_id,
        can_rewrite_steps=v.created_by == "user"
        and v.steps_status is None
        and bool((v.change_set or {}).get("flags")),
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


@router.get("/hidden", response_model=list[HiddenRecipeOut])
def list_hidden(session: DbSession, user: CurrentUser) -> list[HiddenRecipeOut]:
    """Settings, Hidden recipes (step 2b.7, F24): every recipe you hid with Not for me, most recent first.
    DELETE /recipes/{id}/hidden shows one again."""
    rows = hidden.hidden_rows(session, user.id)
    categories = dish_categories(session, [row.version.id for row in rows])
    return [
        HiddenRecipeOut(
            recipe_id=row.recipe.id,
            version_id=row.version.id,
            title=row.version.title,
            kind=row.version.kind,
            dish_category=categories[row.version.id].value,
            hidden_at=row.hidden_at,
        )
        for row in rows
    ]


@router.put("/{recipe_id}/hidden", status_code=204)
def hide(
    recipe_id: int,
    session: DbSession,
    user: CurrentUser,
    plan_meal: Annotated[int | None, Query(description="the plan meal you tapped it on")] = None,
) -> Response:
    """Not for me (F24): leave this recipe out of every future suggestion and plan (plans already made keep
    it). Logs recipe_hidden once; a repeat changes nothing."""
    hidden.set_hidden(session, user.id, recipe_id, True, plan_meal_id=plan_meal)
    session.commit()
    return Response(status_code=204)


@router.delete("/{recipe_id}/hidden", status_code=204)
def unhide(recipe_id: int, session: DbSession, user: CurrentUser) -> Response:
    """Show a hidden recipe again (Undo, or Settings, Hidden recipes). Logs recipe_unhidden once."""
    hidden.set_hidden(session, user.id, recipe_id, False)
    session.commit()
    return Response(status_code=204)


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


# ---------------- step 2b.6: a line's ⋯ (AA5, AA8) ----------------
BatchQuery = Annotated[
    int | None, Query(alias="batch", description="the plan batch the page was opened from")
]


@versions_router.get("/{version_id}/lines/{line_id}/options", response_model=LineOptionsOut)
def line_options(
    version_id: int, line_id: int, session: DbSession, user: CurrentUser, batch: BatchQuery = None
) -> LineOptionsOut:
    """A line's ⋯: Swap it (substitutes from its culinary group or role, with the change per portion in kcal,
    protein and cost), Leave it out (non-essential lines only), I'm out of this (where it would be added to
    a shopping list) and Never use this."""
    opts = edits.line_options(session, user.id, version_id, line_id)
    target = edits.shopping_target(session, user.id, batch, today=search_service.local_now(user).date())
    return LineOptionsOut(
        line_id=opts.line_id,
        ingredient_id=opts.ingredient_id,
        name=opts.name,
        display=opts.display,
        swaps=[
            SwapChoiceOut(
                ingredient_id=c.ingredient_id,
                name=c.name,
                display=c.display,
                numbers=c.numbers,
                note=c.note,
                cooking_note=c.cooking_note,
            )
            for c in opts.swaps
        ],
        leave_out=LeaveOutOut(
            allowed=opts.leave_out.allowed,
            reason=opts.leave_out.reason,
            numbers=opts.leave_out.numbers,
            warning=opts.leave_out.warning,
        ),
        in_pantry=opts.in_pantry,
        never_used=opts.never_used,
        shopping=ShoppingTargetOut(
            plan_id=target.plan_id, list_id=target.list_id, can_add=target.can_add, reason=target.reason
        ),
        pair=BudgetPairOut(
            classic=opts.pair.classic, budget=opts.pair.budget, budget_display=opts.pair.budget_display
        )
        if opts.pair is not None
        else None,
    )


@versions_router.post("/{version_id}/edits", response_model=RecipeEditOut)
def edit_line(version_id: int, body: RecipeEditIn, session: DbSession, user: CurrentUser) -> RecipeEditOut:
    """Swap a line or leave it out, saved as your own version of the recipe (its default from now on). From a
    plan meal (`batch_id`), whether this week's plan can take it (POST
    /plans/{id}/batches/{batch}/use-version)."""
    if body.action == "swap" and body.ingredient_id is None:
        raise ProblemError(422, "Pick a swap", "A swap needs the ingredient to use instead (ingredient_id).")
    result = edits.edit_version(
        session,
        user.id,
        version_id,
        line_id=body.line_id,
        action=body.action,
        ingredient_id=body.ingredient_id,
        batch_id=body.batch_id,
        today=search_service.local_now(user).date(),
    )
    session.commit()
    return RecipeEditOut(
        version=version_out(session, version_view(session, user.id, result.version.id)),
        note=result.note,
        cooking_note=result.cooking_note,
        flagged_steps=result.flagged_steps,
        batch_id=result.batch_id,
        can_update_plan=result.can_update_plan,
        plan_note=result.plan_note,
    )


@versions_router.post("/{version_id}/rewrite-steps", response_model=RecipeVersionOut)
def rewrite_steps(version_id: int, session: DbSession, user: CurrentUser) -> RecipeVersionOut:
    """Rewrite steps for this change: a version of your recipe whose steps are written once, by one LLM call
    when its page opens (POST /recipe-versions/{id}/steps); its lines and times stay as they are."""
    version = edits.rewrite_steps(session, user.id, version_id)
    session.commit()
    return version_out(session, version_view(session, user.id, version.id))


@versions_router.post("/{version_id}/lines/{line_id}/add-to-list", response_model=AddToListOut)
def add_to_list(
    version_id: int, line_id: int, session: DbSession, user: CurrentUser, batch: BatchQuery = None
) -> AddToListOut:
    """I'm out of this: the line's ingredient on your shopping list (the plan the page came from, else your
    current plan), as much as that plan's batch uses, in whole packages at your stores."""
    item, added, target = edits.add_to_list(
        session, user.id, version_id, line_id, batch_id=batch, today=search_service.local_now(user).date()
    )
    session.commit()
    out = plan_service.one_grocery_item(session, item)
    what = out.to_buy or out.needed
    cost = f" ({out.estimated_cost_display})" if out.estimated_cost_display else ""
    message = (
        f"Added {what} {out.name} to your shopping list{cost}."
        if added
        else f"{out.name} is already on your shopping list."
    )
    assert target.plan_id is not None and target.list_id is not None
    return AddToListOut(
        added=added, plan_id=target.plan_id, list_id=target.list_id, item=out, message=message
    )
