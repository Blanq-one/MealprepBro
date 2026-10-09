"""Load what the constraint builder needs from the database (settings, diet status, stores, preferences)."""

from sqlalchemy.orm import Session

from app.domain.exclusions import Preference
from app.planning.constraint_builder import DietInputs, build_constraints
from app.schemas.constraints import PlanConstraints
from app.schemas.plans import PlanRequest
from app.services.exclusions import diet_status, preferences
from app.services.pricing import active_stores
from app.services.settings import load_settings


def diet_inputs(session: Session, user_id: int) -> DietInputs:
    status = diet_status(session, user_id)
    prefs = preferences(session, user_id)
    return DietInputs(
        statuses={i: r.status for i, r in status.results.items()},
        caps=status.caps,
        disliked_ids=frozenset(i for i, p in prefs.items() if p is Preference.DISLIKE),
        favorite_recipe_ids=frozenset(),  # favorites arrive in Phase 3
    )


def constraints_for(session: Session, user_id: int, request: PlanRequest) -> PlanConstraints:
    settings = load_settings(session, user_id)
    stores = {s.name: s.id for s in active_stores(session, "grocery")}
    others = tuple(s.id for s in active_stores(session, "other"))
    return build_constraints(settings, request, diet_inputs(session, user_id), stores, others)
