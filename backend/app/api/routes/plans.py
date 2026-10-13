from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, LLMClientFactory, LLMClock, LLMSettings, SessionFactory
from app.cook import search as search_service
from app.db.models import PlanCookBatch
from app.planning.persistence import PlanNotFoundError
from app.schemas.plans import (
    GenerationRunOut,
    GroceryListOut,
    PlanListItemOut,
    PlanRequest,
    PlanStreamEvent,
    PlanSummaryOut,
    PlanUpdateOut,
    SwapIn,
    SwapOptionsIn,
    SwapOut,
    SwapStreamEvent,
    UseVersionIn,
)
from app.services import plans as service
from app.services import swap as swap_service
from app.services.plan_stream import plan_events
from app.services.plan_view import swapped_message

router = APIRouter(prefix="/api/v1", tags=["plans"])

NDJSON = "application/x-ndjson"


@router.post(
    "/plans",
    response_class=StreamingResponse,
    responses={200: {"model": PlanStreamEvent, "content": {NDJSON: {}}, "description": "NDJSON event lines"}},
)
def create_plan(
    *,
    body: PlanRequest,
    user: CurrentUser,
    session_factory: SessionFactory,
    client_factory: LLMClientFactory,
) -> StreamingResponse:
    """Plan a week inside this request. The response is a stream of JSON lines (`PlanStreamEvent`):
    `started` with the run id, `progress` and `heartbeat` lines while it works, and one final `result` with
    the plan summary or the problem. The run record is kept (`GET /generation-runs/{id}`)."""
    events = plan_events(session_factory, user.id, body, client_factory)
    return StreamingResponse(
        events,
        media_type=NDJSON,
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/plans", response_model=list[PlanListItemOut])
def list_plans(
    session: DbSession, user: CurrentUser, limit: int = Query(default=10, ge=1, le=50)
) -> list[PlanListItemOut]:
    """Your recent plans, newest first. `is_current` marks the one the app opens on: the active plan for
    this week, else the latest active plan, else the latest draft."""
    return service.list_plans(session, user.id, limit)


@router.get("/generation-runs/{run_id}", response_model=GenerationRunOut)
def get_run(run_id: int, session: DbSession, user: CurrentUser) -> GenerationRunOut:
    return service.run_view(session, user.id, run_id)


@router.get("/plans/{plan_id}", response_model=PlanSummaryOut)
def get_plan(plan_id: int, session: DbSession, user: CurrentUser) -> PlanSummaryOut:
    return service.plan_summary(session, user.id, plan_id)


@router.post("/plans/{plan_id}/accept", response_model=PlanSummaryOut)
def accept_plan(
    plan_id: int,
    session: DbSession,
    user: CurrentUser,
    replace_overlapping: bool = Query(default=False),
) -> PlanSummaryOut:
    """Make a draft your current plan. If active plans overlap its days, the answer is 409 with
    `overlapping` (each plan's id, days, meals and the "Replace your current plan (…)?" question) unless
    `replace_overlapping=true`, which replaces them."""
    out = service.accept(session, user.id, plan_id, replace_overlapping=replace_overlapping)
    session.commit()
    return out


@router.post(
    "/plans/{plan_id}/meals/{meal_id}/swap-options",
    response_class=StreamingResponse,
    responses={200: {"model": SwapStreamEvent, "content": {NDJSON: {}}, "description": "NDJSON event lines"}},
)
def swap_options(
    plan_id: int,
    meal_id: int,
    *,
    body: SwapOptionsIn,
    user: CurrentUser,
    session_factory: SessionFactory,
    client_factory: LLMClientFactory,
    clock: LLMClock,
    llm_settings: LLMSettings,
) -> StreamingResponse:
    """Swap's sheet (E5, step 2b.6): 3-5 other meals that fit this slot, day, fridge or freezer and time
    rules, with what each adds to the groceries, as a stream of JSON lines (`SwapStreamEvent`). Recipes in
    `exclude_version_ids` (already swapped away) are left out; `allow_llm` ("Write a new one") makes one ideas
    call first, a rate-limit wait shown as `wait_s`; after Done shopping, options use your pantry unless
    `allow_buying`."""
    events = swap_service.swap_option_events(
        session_factory,
        user.id,
        plan_id,
        meal_id,
        body,
        client_factory=client_factory,
        clock=clock,
        settings=llm_settings,
    )
    return StreamingResponse(
        events, media_type=NDJSON, headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    )


@router.post("/plans/{plan_id}/meals/{meal_id}/swap", response_model=SwapOut)
def swap_meal(plan_id: int, meal_id: int, body: SwapIn, session: DbSession, user: CurrentUser) -> SwapOut:
    """Replace just this meal with the option you tapped. The plan is saved as a new version that
    supersedes this one (same status, grocery check-offs carried over); `undo_plan_id` is the version Undo
    brings back."""
    today = search_service.local_now(user).date()  # the Cook flow's clock, as meal prep
    result = swap_service.apply_swap(
        session,
        user.id,
        plan_id,
        meal_id,
        body.version_id,
        today=today,
        allow_buying=body.allow_buying,
        offered=body.offered_version_ids,
        swapped_away=body.exclude_version_ids,
    )
    session.commit()
    return SwapOut(
        plan_id=result.plan.id,
        undo_plan_id=result.undo_plan_id,
        plan=service.plan_summary(session, user.id, result.plan.id),
        plan_meal_id=result.plan_meal_id,
        message=swapped_message(result.also_changed),
        also_changed=result.also_changed,
    )


@router.post("/plans/{plan_id}/swap/undo", response_model=PlanSummaryOut)
def undo_swap(plan_id: int, session: DbSession, user: CurrentUser) -> PlanSummaryOut:
    """Undo a swap: the version before it comes back exactly as it was (409 once you've cooked or shopped
    since)."""
    old = swap_service.undo_swap(session, user.id, plan_id)
    session.commit()
    return service.plan_summary(session, user.id, old.id)


@router.post("/plans/{plan_id}/batches/{batch_id}/use-version", response_model=PlanUpdateOut)
def use_version(
    plan_id: int, batch_id: int, body: UseVersionIn, session: DbSession, user: CurrentUser
) -> PlanUpdateOut:
    """Also update this week's plan (AA8): the batch (and every meal it feeds) switches to your version of its
    recipe; nutrition, cost and the shopping list are recomputed and checked, the batch's portion size
    re-solved if a limit breaks. Cooked batches keep the recipe they were cooked with (409 says why)."""
    batch = session.get(PlanCookBatch, batch_id)
    if batch is None or batch.meal_plan_id != plan_id:
        raise PlanNotFoundError(f"cook batch {batch_id} not found in plan {plan_id}")
    result = swap_service.use_version(
        session, user.id, batch_id, body.version_id, today=search_service.local_now(user).date()
    )
    session.commit()
    return PlanUpdateOut(
        plan_id=result.plan.id,
        undo_plan_id=result.undo_plan_id,
        plan=service.plan_summary(session, user.id, result.plan.id),
        message=result.message,
        also_changed=result.also_changed,
    )


@router.get("/plans/{plan_id}/grocery-list", response_model=GroceryListOut)
def grocery_list(
    plan_id: int,
    session: DbSession,
    user: CurrentUser,
    group_by: Literal["store", "category", "none"] = Query(default="store"),
) -> GroceryListOut:
    return service.grocery_view(session, user.id, plan_id, group_by=group_by)
