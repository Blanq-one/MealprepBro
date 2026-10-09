"""Candidate-exposure log (Phase 2, deliverable 7): what the solver was offered, for the future ranker.

A succeeded run writes one `plan_candidate` row per candidate recipe for this week's slots: every recipe
offered to the solver (seed, saved, favorite, your version, or generated in this run) and every recipe
filtered out before solving, with the reason. Each row carries the Phase 1 heuristic score (the per-portion
terms of the solver's objective, recomputed here by the same weights), its components, a feature snapshot,
and whether the plan used it. Failed and infeasible runs write nothing, so the log never holds a partial run.
"""

from collections import defaultdict
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PlanCandidate, Recipe, RecipeVersion
from app.planning.problem import CandidateRecipe, ExcludedRecipe, PlanningProblem
from app.planning.rounded import RoundedPlan
from app.planning.solver.objective import nutrient_score, weights_for

# When a recipe is left out for several reasons, the log names the first of these.
FILTER_PRIORITY = (
    "held",
    "frequency_cap",
    "excluded",
    "equipment",
    "time",
    "unpriced",
    "nutrition_incomplete",
    "conversion",
)
FEATURE_NUTRIENTS = ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fiber_g", "iron_mg")
Q4 = Decimal("0.0001")


def _source(
    origin: str, recipe_id: int, version_id: int, favorites: frozenset[int], new: frozenset[int]
) -> str:
    if version_id in new:
        return "llm_new"
    if recipe_id in favorites:
        return "favorite"
    if origin == "user":
        return "user_version"
    if origin == "seed":
        return "seed"
    return "saved"


def filtered_reason(excluded: ExcludedRecipe) -> str:
    codes = excluded.codes or ("excluded",)
    return min(
        codes, key=lambda c: FILTER_PRIORITY.index(c) if c in FILTER_PRIORITY else len(FILTER_PRIORITY)
    )


def heuristic_score(problem: PlanningProblem, candidate: CandidateRecipe) -> tuple[Decimal, dict[str, Any]]:
    """The candidate's per-portion objective terms at its default size: nutrient priorities (normalized to the
    best candidate), favorite and dislike, the never-favored tie-break, and its cost per portion."""
    c = problem.constraints
    w = weights_for(c.grocery_mode)
    pool = problem.candidates
    best = max((nutrient_score(r, c.nutrition_priority) for r in pool), default=Decimal(0)) or Decimal(1)
    parts: dict[str, Decimal] = {}
    if not candidate.never_favored:
        parts["primary"] = Decimal(str(w.primary)) * nutrient_score(candidate, c.nutrition_priority) / best
        if c.secondary_priority is not None:
            best2 = max(
                (nutrient_score(r, c.secondary_priority) for r in pool), default=Decimal(0)
            ) or Decimal(1)
            parts["secondary"] = (
                Decimal(str(w.secondary)) * nutrient_score(candidate, c.secondary_priority) / best2
            )
        if candidate.is_favorite:
            parts["favorite"] = Decimal(str(w.preference))
    else:
        parts["never_favored"] = -Decimal(str(w.never_favored_tiebreak))
    if candidate.has_disliked:
        parts["disliked"] = -Decimal(str(w.preference))
    if candidate.cost_cents_per_portion is not None:
        parts["cost"] = -Decimal(str(w.cost_per_dollar)) * candidate.cost_cents_per_portion / 100
    rounded = {k: v.quantize(Q4, ROUND_HALF_UP) for k, v in parts.items()}
    components: dict[str, Any] = {k: str(v) for k, v in rounded.items()}
    if candidate.cost_cents_per_portion is None:
        components["cost_unknown"] = True
    return sum(rounded.values(), Decimal(0)), components


def features(candidate: CandidateRecipe) -> dict[str, Any]:
    p = candidate.per_portion
    return {
        **{k: str(p[k].quantize(Q4, ROUND_HALF_UP)) for k in FEATURE_NUTRIENTS if k in p},
        "heme_iron_mg_estimated": str(candidate.heme_iron_mg.quantize(Q4, ROUND_HALF_UP)),
        "cost_cents_per_portion": str(candidate.cost_cents_per_portion.quantize(Q4, ROUND_HALF_UP))
        if candidate.cost_cents_per_portion is not None
        else None,
        "active_minutes": candidate.active_minutes,
        "total_minutes": candidate.total_minutes,
        "mood": candidate.mood.value,
        "equipment": sorted(e.value for e in candidate.equipment),
        "freezer_friendly": candidate.freezer_friendly,
        "base_servings": candidate.base_servings,
        "origin": candidate.origin,
        "is_draft": candidate.is_draft,
        "is_favorite": candidate.is_favorite,
        "has_disliked": candidate.has_disliked,
        "never_favored": candidate.never_favored,
        "ingredient_ids": sorted(candidate.ingredient_ids),
        "title": candidate.title,
    }


def _origins(session: Session, version_ids: Iterable[int]) -> dict[int, tuple[str, int]]:
    ids = sorted(set(version_ids))
    if not ids:
        return {}
    rows = session.execute(
        select(RecipeVersion.id, Recipe.origin, Recipe.id)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .where(RecipeVersion.id.in_(ids))
    ).tuples()
    return {vid: (origin, rid) for vid, origin, rid in rows}


def log_exposures(
    session: Session,
    run_id: int,
    plan_id: int,
    problem: PlanningProblem,
    plan: RoundedPlan,
    *,
    new_version_ids: frozenset[int] = frozenset(),
) -> list[PlanCandidate]:
    c = problem.constraints
    portions: dict[int, int] = defaultdict(int)
    for batch in plan.batches:
        portions[batch.version_id] += batch.portions
    origins = _origins(session, [e.version_id for e in problem.excluded])
    rows: list[PlanCandidate] = []
    for candidate in problem.candidates:
        score, components = heuristic_score(problem, candidate)
        rows.append(
            PlanCandidate(
                generation_run_id=run_id,
                meal_plan_id=plan_id,
                recipe_version_id=candidate.version_id,
                source=_source(
                    candidate.origin,
                    candidate.recipe_id,
                    candidate.version_id,
                    c.favorite_recipe_ids,
                    new_version_ids,
                ),
                eligible_slots=sorted(s.value for s in candidate.meal_slots),
                filtered_reason=None,
                heuristic_score=score,
                score_components=components,
                features=features(candidate),
                selected=candidate.version_id in portions,
                portions_selected=portions.get(candidate.version_id, 0),
            )
        )
    for excluded in problem.excluded:
        origin, recipe_id = origins.get(excluded.version_id, ("saved", 0))
        rows.append(
            PlanCandidate(
                generation_run_id=run_id,
                meal_plan_id=plan_id,
                recipe_version_id=excluded.version_id,
                source=_source(
                    origin, recipe_id, excluded.version_id, c.favorite_recipe_ids, new_version_ids
                ),
                eligible_slots=sorted(s.value for s in excluded.meal_slots),
                filtered_reason=filtered_reason(excluded),
                heuristic_score=None,
                score_components=None,
                features={
                    "title": excluded.title,
                    "filter_codes": list(excluded.codes),
                    "reasons": list(excluded.reasons),
                },
                selected=False,
                portions_selected=0,
            )
        )
    session.add_all(rows)
    session.flush()
    return rows
