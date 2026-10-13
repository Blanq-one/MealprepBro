"""POST /cook/meal-prep (E4, FLOW_SPEC C1–C6, step 2b.5): your meal-prep answers become a plan request
(app/cook/prep.py) and run through the weekly planner inside the request, streamed like POST /plans with the
friendly building steps (constraints, candidates, generating, solving, pricing, validating).

A meal-prep search is remembered (cook_search, mode "prep") for "Same as last time", with its run and plan.
Gaps are filled with the ideas pass (F20); "have it" items marked Save to pantry are written to your pantry
first. The plan is a draft of kind "meal_prep" until you accept it (overlap-aware, E6).
"""

from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import date

from sqlalchemy.orm import Session

from app.cook.answers import answers_hash
from app.cook.prep import PrepPlan, resolve_prep
from app.cook.tiers import tier_floor
from app.db.models import CookSearch, Ingredient
from app.domain.enums import StorageLocation
from app.planning.orchestrator import PlanOutcome
from app.schemas.cook import CookAnswers
from app.services import plans as plan_service
from app.services.inventory import LotInput, add_lots
from app.services.plan_stream import PREP_STAGE_MESSAGES, plan_events
from app.services.settings import load_settings

MODE_PREP = "prep"
MEAL_PREP = "meal_prep"  # meal_plan.kind and generation_run.purpose


def prepare(session: Session, user_id: int, answers: CookAnswers, today: date) -> tuple[PrepPlan, CookSearch]:
    """Resolve the answers (a PrepAnswersError says what to change), write the Save-to-pantry items, and
    remember the search. The caller commits."""
    plan = resolve_prep(answers, load_settings(session, user_id), today)
    if (floor := tier_floor(session, user_id, answers, today)) is not None:
        # the tier you tapped costs the same or more than the one below, as its card did (AC3)
        plan = replace(plan, request=plan.request.model_copy(update={"regular_floor_cents": floor}))
    if plan.save_to_pantry:
        add_lots(
            session,
            user_id,
            [
                LotInput(
                    ingredient_id=lot.ingredient_id,
                    quantity=lot.quantity,
                    unit=lot.unit,
                    location=_location(session, lot.ingredient_id),
                    acquired_on=today,
                    reason="manual_adjust",
                )
                for lot in plan.save_to_pantry
            ],
        )
    digest = answers_hash(answers)
    search = CookSearch(
        user_id=user_id,
        mode=MODE_PREP,
        answers=answers.model_dump(mode="json"),
        answers_hash=digest,
        cache_key=digest,  # a meal-prep plan isn't served from a cache: your pantry and prices move
        status="running",
        results={"header": plan.header},
    )
    session.add(search)
    session.flush()
    return plan, search


def _location(session: Session, ingredient_id: int) -> StorageLocation:
    ingredient = session.get(Ingredient, ingredient_id)
    where = ingredient.typical_location if ingredient is not None else None
    return StorageLocation(where) if where in {s.value for s in StorageLocation} else StorageLocation.PANTRY


def meal_prep_events(
    session_factory: Callable[[], Session],
    user_id: int,
    plan: PrepPlan,
    search_id: int,
    client_factory: plan_service.ClientFactory,
    *,
    today: date,
) -> Iterator[str]:
    def started(session: Session, run_id: int) -> None:
        search = session.get(CookSearch, search_id)
        if search is not None:
            search.generation_run_id = run_id

    def finished(session: Session, outcome: PlanOutcome) -> None:
        search = session.get(CookSearch, search_id)
        if search is None:
            return
        search.status = "done" if outcome.status == "succeeded" else "failed"
        search.meal_plan_id = outcome.plan_id
        search.results = {**(search.results or {}), "status": outcome.status}

    return plan_events(
        session_factory,
        user_id,
        plan.request,
        client_factory,
        purpose=MEAL_PREP,
        kind=MEAL_PREP,
        ideas=True,
        today=today,
        messages=PREP_STAGE_MESSAGES,
        on_started=started,
        on_outcome=finished,
    )
