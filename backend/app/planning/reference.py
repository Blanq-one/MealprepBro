"""What the plan validator recomputes from: a fresh load from the database, independent of the solver's
in-memory problem (deliverable 15: "recomputes every number from the DB")."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Nutrient, Recipe, RecipeIngredient, RecipeStep, RecipeVersion
from app.domain.enums import Equipment, MealSlot, RecipeMood
from app.domain.exclusions import ExclusionStatus
from app.domain.food_safety import SafetyCategory
from app.planning.loader import load_ingredient_plans, version_lines
from app.planning.problem import IngredientPlan, RecipeLine
from app.planning.rendering import StepInput
from app.schemas.constraints import PlanConstraints, ResolvedFrequencyCap
from app.services.exclusions import diet_status
from app.services.ingredient_data import load_ingredients


@dataclass(frozen=True)
class RefRecipe:
    version_id: int
    recipe_id: int
    title: str
    description: str
    origin: str
    is_draft: bool
    base_servings: int
    meal_slots: frozenset[MealSlot]
    mood: RecipeMood
    active_minutes: int
    equipment: frozenset[Equipment]
    freezer_friendly: bool
    lines: tuple[RecipeLine, ...]
    steps: tuple[StepInput, ...]
    preparations: Mapping[int, str | None] = field(default_factory=dict)  # recipe_ingredient id -> text


@dataclass(frozen=True)
class ReferenceData:
    recipes: Mapping[int, RefRecipe]
    ingredients: Mapping[int, IngredientPlan]
    safety: Mapping[int, SafetyCategory | None]
    excluded_ingredient_ids: frozenset[int]  # recomputed from tags, decisions and caps
    caps: tuple[ResolvedFrequencyCap, ...]
    daily_values: Mapping[str, Decimal]


def load_recipes(session: Session, version_ids: Iterable[int]) -> dict[int, RefRecipe]:
    ids = sorted(set(version_ids))
    if not ids:
        return {}
    lines = version_lines(session, ids)
    steps: dict[int, list[StepInput]] = {i: [] for i in ids}
    for step in session.scalars(
        select(RecipeStep)
        .where(RecipeStep.recipe_version_id.in_(ids))
        .order_by(RecipeStep.recipe_version_id, RecipeStep.position)
    ):
        steps[step.recipe_version_id].append(
            StepInput(
                step.section,
                step.text,
                step.duration_minutes,
                step.appliance_temp_f,
                step.doneness_check_ingredient_id,
            )
        )
    preps: dict[int, dict[int, str | None]] = {i: {} for i in ids}
    for row in session.scalars(select(RecipeIngredient).where(RecipeIngredient.recipe_version_id.in_(ids))):
        preps[row.recipe_version_id][row.id] = row.preparation
    out = {}
    for version, recipe in session.execute(
        select(RecipeVersion, Recipe)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .where(RecipeVersion.id.in_(ids))
    ).all():
        out[version.id] = RefRecipe(
            version_id=version.id,
            recipe_id=recipe.id,
            title=version.title,
            description=version.description,
            origin=recipe.origin,
            is_draft=version.is_draft,
            base_servings=version.base_servings,
            meal_slots=frozenset(MealSlot(s) for s in version.meal_slots),
            mood=RecipeMood(version.mood),
            active_minutes=version.active_minutes,
            equipment=frozenset(Equipment(e) for e in version.equipment),
            freezer_friendly=version.freezer_friendly,
            lines=tuple(lines.get(version.id, [])),
            steps=tuple(steps[version.id]),
            preparations=preps[version.id],
        )
    return out


def daily_values(session: Session) -> dict[str, Decimal]:
    return {n.code: n.daily_value for n in session.scalars(select(Nutrient)) if n.daily_value is not None}


def load_reference(
    session: Session, user_id: int, constraints: PlanConstraints, version_ids: Iterable[int]
) -> ReferenceData:
    recipes = load_recipes(session, version_ids)
    ingredient_ids = {line.ingredient_id for r in recipes.values() for line in r.lines}
    plans = load_ingredient_plans(
        session, user_id, ingredient_ids, constraints.store_ids, constraints.always_have_ingredient_ids
    )
    data = load_ingredients(session, ingredient_ids)
    status = diet_status(session, user_id)
    excluded = frozenset(i for i, r in status.results.items() if r.status is not ExclusionStatus.ALLOWED)
    caps = tuple(
        ResolvedFrequencyCap(
            label=c.label,
            member_ingredient_ids=c.member_ids,
            max_meals_per_week=c.max_meals_per_week,
            never_favor=c.never_favor,
        )
        for c in status.caps
    )
    return ReferenceData(
        recipes=recipes,
        ingredients=plans,
        safety={i: d.safety_category for i, d in data.items()},
        excluded_ingredient_ids=excluded,
        caps=caps,
        daily_values=daily_values(session),
    )
