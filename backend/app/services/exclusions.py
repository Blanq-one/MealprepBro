"""Diet-rule status for every ingredient, for one user: tags + explicit decisions + frequency caps."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngredientPreference
from app.domain.exclusions import ExclusionResult, Preference, resolve
from app.domain.frequency_caps import FrequencyCap, ResolvedCap, resolve_caps, zero_cap_exclusions
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.settings import load_settings


@dataclass(frozen=True)
class DietStatus:
    results: dict[int, ExclusionResult]
    caps: tuple[ResolvedCap, ...]

    def caps_for(self, ingredient_id: int) -> tuple[str, ...]:
        return tuple(cap.label for cap in self.caps if ingredient_id in cap.member_ids)


def preferences(session: Session, user_id: int) -> dict[int, Preference]:
    rows = session.scalars(select(IngredientPreference).where(IngredientPreference.user_id == user_id))
    return {row.ingredient_id: Preference(row.preference) for row in rows}


def diet_status(session: Session, user_id: int, data: dict[int, IngredientData] | None = None) -> DietStatus:
    settings = load_settings(session, user_id)
    data = data if data is not None else load_ingredients(session)
    caps = resolve_caps(
        [
            FrequencyCap(c.label, c.target_type, c.target, c.max_meals_per_week, c.never_favor)
            for c in settings.frequency_caps
        ],
        [d.cap_view for d in data.values()],
    )
    results = resolve(
        [d.tagged for d in data.values()],
        frozenset(settings.excluded_diet_tags),
        preferences(session, user_id),
        zero_cap_exclusions(caps),
    )
    return DietStatus(results=results, caps=caps)
