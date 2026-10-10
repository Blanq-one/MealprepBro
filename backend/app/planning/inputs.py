"""Load what the constraint builder needs from the database (settings, diet status, stores, preferences,
favorites and Always-have items)."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient
from app.domain.exclusions import Preference
from app.planning.constraint_builder import DietInputs, build_constraints
from app.schemas.constraints import PlanConstraints
from app.schemas.plans import PlanRequest
from app.services.exclusions import diet_status, preferences
from app.services.favorites import favorite_recipe_ids
from app.services.pricing import active_stores
from app.services.settings import ALWAYS_HAVE_SLUGS, load_settings


def always_have_ids(session: Session, slugs: Iterable[str]) -> frozenset[int]:
    wanted = set(slugs) | set(ALWAYS_HAVE_SLUGS)
    return frozenset(
        session.scalars(
            select(Ingredient.id).where(Ingredient.slug.in_(wanted), Ingredient.archived_at.is_(None))
        )
    )


def diet_inputs(session: Session, user_id: int, always_have: Iterable[str] = ()) -> DietInputs:
    status = diet_status(session, user_id)
    prefs = preferences(session, user_id)
    return DietInputs(
        statuses={i: r.status for i, r in status.results.items()},
        caps=status.caps,
        disliked_ids=frozenset(i for i, p in prefs.items() if p is Preference.DISLIKE),
        favorite_recipe_ids=favorite_recipe_ids(session, user_id),
        always_have_ids=always_have_ids(session, always_have),
    )


def constraints_for(session: Session, user_id: int, request: PlanRequest) -> PlanConstraints:
    settings = load_settings(session, user_id)
    stores = {s.name: s.id for s in active_stores(session, "grocery")}
    others = tuple(s.id for s in active_stores(session, "other"))
    diet = diet_inputs(session, user_id, settings.always_have)
    return build_constraints(settings, request, diet, stores, others)
