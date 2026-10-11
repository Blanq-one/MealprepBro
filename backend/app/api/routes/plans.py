from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, LLMClientFactory, SessionFactory
from app.schemas.plans import (
    GenerationRunOut,
    GroceryListOut,
    PlanListItemOut,
    PlanRequest,
    PlanStreamEvent,
    PlanSummaryOut,
)
from app.services import plans as service
from app.services.plan_stream import plan_events

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


@router.get("/plans/{plan_id}/grocery-list", response_model=GroceryListOut)
def grocery_list(
    plan_id: int,
    session: DbSession,
    user: CurrentUser,
    group_by: Literal["store", "category", "none"] = Query(default="store"),
) -> GroceryListOut:
    return service.grocery_view(session, user.id, plan_id, group_by=group_by)
