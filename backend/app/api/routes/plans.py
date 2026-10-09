from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Query

from app.api.deps import CurrentUser, DbSession, LLMClientFactory, SessionFactory
from app.schemas.plans import GenerationRunOut, GroceryListOut, PlanRequest, PlanSummaryOut, RunAccepted
from app.services import plans as service

router = APIRouter(prefix="/api/v1", tags=["plans"])


@router.post("/plans", response_model=RunAccepted, status_code=202)
def create_plan(
    *,
    body: PlanRequest,
    background: BackgroundTasks,
    session: DbSession,
    user: CurrentUser,
    session_factory: SessionFactory,
    client_factory: LLMClientFactory,
) -> RunAccepted:
    """Start planning a week. Poll the returned run until it is succeeded, infeasible or failed."""
    run = service.start_run(session, user.id, body)
    session.commit()
    background.add_task(service.execute_run, session_factory, run.id, body, client_factory)
    return RunAccepted(run_id=run.id, status=run.status, status_url=f"/api/v1/generation-runs/{run.id}")


@router.get("/generation-runs/{run_id}", response_model=GenerationRunOut)
def get_run(run_id: int, session: DbSession, user: CurrentUser) -> GenerationRunOut:
    return service.run_view(session, user.id, run_id)


@router.get("/plans/{plan_id}", response_model=PlanSummaryOut)
def get_plan(plan_id: int, session: DbSession, user: CurrentUser) -> PlanSummaryOut:
    return service.plan_summary(session, user.id, plan_id)


@router.post("/plans/{plan_id}/accept", response_model=PlanSummaryOut)
def accept_plan(plan_id: int, session: DbSession, user: CurrentUser) -> PlanSummaryOut:
    out = service.accept(session, user.id, plan_id)
    session.commit()
    return out


@router.get("/plans/{plan_id}/grocery-list", response_model=GroceryListOut)
def grocery_list(
    plan_id: int,
    session: DbSession,
    user: CurrentUser,
    group_by: Literal["store", "none"] = Query(default="store"),
) -> GroceryListOut:
    return service.grocery_view(session, user.id, plan_id, group_by_store=group_by == "store")
