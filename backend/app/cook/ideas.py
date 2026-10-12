"""New ideas for a meal now (FLOW_SPEC §13.5, §14): the request the ideas pass sends for your search, and what
an ideas call's outcome means on screen.

The meal-now request adds, as approved:
  * must use: up to 6 of your items, open packages and soonest-expiring first, then proteins;
  * may buy: your "could buy" items;
  * goal hints as ingredient directions (never as claims; the prose filter still blocks claims);
  * avoid: the titles already on screen;
  * a narrowed vocabulary: your items, could-buys, Always-have and assume-in-stock staples, plus up to 30
    common allowed ingredients your stores price (by how often your recipes use them). The never-use list is
    unchanged. Every name is a short name (domain/prompt_names.py).
A failed call never errors: saved results stay, with a note and status `partial`; a wait too long for the
request also gives `retry_after_s`. Only the daily guard gives the "back tomorrow" note.
"""

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.cook.answers import MealNowQuery
from app.cook.pool import Pool, store_ids
from app.db.models import PriceObservation, Product, Recipe, RecipeIngredient, RecipeVersion
from app.domain.cook_time import MOOD_MAX_ACTIVE_MINUTES
from app.domain.enums import Equipment, RecipeKind
from app.domain.exclusions import ExclusionStatus
from app.llm.client import LLMClient
from app.llm.errors import (
    LLMBudgetExceededError,
    LLMConfigError,
    LLMError,
    LLMRateLimitedError,
    LLMWaitTooLongError,
)
from app.llm.pacing import Clock, Deadline
from app.llm.structured import LLMRunContext
from app.planning.candidates import BASE_SERVINGS, TORTILLA_RULE
from app.planning.ideas import IdeaGenerator, IdeaRequest, IdeasOutcome
from app.planning.resolver import IngredientResolver
from app.schemas.cook import GoalTile
from app.schemas.settings import UserSettings
from app.services.exclusions import diet_status

log = logging.getLogger(__name__)

MUST_USE_MAX = 6
COMMON_MAX = 30
AVOID_MAX = 25
BEEF_NEVER = "beef and anything made from beef (broth, stock, tallow, bouillon, bovine gelatin)"
GOAL_HINTS: dict[GoalTile, str] = {
    GoalTile.HIGH_PROTEIN: "favor protein-rich ingredients such as eggs, chicken, Greek yogurt, chickpeas",
    GoalTile.HIGH_CARB: "favor carbohydrate-rich ingredients such as rice, potatoes, oats, tortillas",
    GoalTile.IRON_RICH: "favor iron-containing ingredients such as spinach, lentils, chickpeas, chicken",
    GoalTile.LOW_CALORIE: "favor vegetables and lean proteins, with little oil, butter or cream",
    GoalTile.CHEAP: "favor everyday staples and the items listed to use; add few other ingredients",
}
NOTE_FAILED = "I couldn't write new ideas just now. These are your saved ones."
NOTE_DAILY = "That's today's new-idea allowance; back tomorrow."
NOTE_WAITING = "The recipe service needs a short breather. Your saved ones are here meanwhile."
NOTE_NOT_SET_UP = "New ideas aren't set up yet ({reason}). These are your saved ones."

ClientFactory = Callable[[], LLMClient | None]


@dataclass(frozen=True)
class LLMAccess:
    """How a request reaches the LLM: the configured client (tests pass a fake), settings and clock."""

    client_factory: ClientFactory
    settings: Settings
    clock: Clock

    def client(self) -> tuple[LLMClient | None, str | None]:
        """(the client, why there's none)."""
        try:
            client = self.client_factory()
        except LLMConfigError as exc:
            return None, str(exc)
        return client, None if client is not None else "no LLM client is configured"

    def context(
        self,
        session: Session,
        client: LLMClient,
        run_id: int,
        *,
        deadline: Deadline,
        on_wait: Callable[[float], None] | None = None,
    ) -> LLMRunContext:
        return LLMRunContext(
            client, session, self.settings, run_id, self.clock, deadline=deadline, on_wait=on_wait
        )


@dataclass
class IdeasRun:
    """What one ideas call meant for the screen."""

    status: Literal["succeeded", "partial"] = "succeeded"
    created: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    retry_after_s: int | None = None
    error_code: str | None = None


def wait_seconds(seconds: float | None) -> int:
    return max(1, math.ceil(seconds or 1))


def common_ingredients(
    session: Session, user_id: int, stores: tuple[int, ...], candidates: set[int], limit: int = COMMON_MAX
) -> list[int]:
    """Up to `limit` allowed ingredients your stores price, by how often your recipes use them."""
    priced = set(
        session.scalars(
            select(Product.ingredient_id)
            .join(PriceObservation, PriceObservation.product_id == Product.id)
            .where(PriceObservation.store_id.in_(stores), Product.archived_at.is_(None))
            .distinct()
        )
    )
    counts = session.execute(
        select(RecipeIngredient.ingredient_id, func.count())
        .join(RecipeVersion, RecipeVersion.id == RecipeIngredient.recipe_version_id)
        .join(Recipe, Recipe.default_version_id == RecipeVersion.id)
        .where(
            Recipe.user_id == user_id,
            Recipe.archived_at.is_(None),
            RecipeVersion.kind == RecipeKind.DISH.value,
        )
        .group_by(RecipeIngredient.ingredient_id)
    ).tuples()
    ranked = sorted(
        ((n, i) for i, n in counts if i in priced and i in candidates), key=lambda t: (-t[0], t[1])
    )
    return [i for _, i in ranked[:limit]]


def meal_now_request(
    session: Session,
    user_id: int,
    settings: UserSettings,
    query: MealNowQuery,
    pool: Pool,
    *,
    resolver: IngredientResolver,
    on_screen: list[str],
) -> IdeaRequest:
    status = diet_status(session, user_id, resolver.data)
    allowed = {i for i, r in resolver.statuses.items() if r.status is ExclusionStatus.ALLOWED}
    never_favored = {
        i for cap in status.caps if cap.never_favor and cap.max_meals_per_week > 0 for i in cap.member_ids
    }
    usable = allowed - never_favored - {i for i, d in resolver.data.items() if d.slug == "chapati"}
    staples = {i for i, d in resolver.data.items() if d.assume_in_stock}
    yours = set(pool.stock) & usable
    stores, _ = store_ids(session, settings)
    common = common_ingredients(session, user_id, stores, usable)
    vocabulary = (
        yours | (set(query.could_buy) & usable) | (pool.always_have_ids & usable) | staples | set(common)
    )
    vocabulary &= usable

    def order(i: int) -> tuple[bool, date, bool, str]:
        s = pool.stock[i]
        return (
            not s.opened,
            s.earliest_expiry or date.max,
            resolver.data[i].category != "protein",
            resolver.data[i].name,
        )

    must = sorted(yours - staples - pool.always_have_ids, key=order)[:MUST_USE_MAX]
    goals = list(dict.fromkeys([*query.goals, *(t.goal for t in query.nutrition)]))
    tortilla = next((i for i, d in resolver.data.items() if d.slug == "flour-tortilla-small"), None)
    blocked = {i: label for label, members in pool.rules.cap_used_up.items() for i in members}
    return IdeaRequest(
        slot=query.slot,
        mood=query.mood,
        base_servings=BASE_SERVINGS.get(query.slot, 2),
        equipment=frozenset(Equipment(e) for e in settings.equipment),
        vocabulary=tuple(sorted({resolver.short_name(i) for i in vocabulary})),
        never_use=(
            BEEF_NEVER,
            *sorted({resolver.short_name(i) for i in resolver.data if i not in allowed}),
        ),
        max_active_minutes=MOOD_MAX_ACTIVE_MINUTES[query.mood],
        max_total_minutes=query.quick_minutes,
        kcal_per_portion=int(query.kcal_target) if query.kcal_target is not None else None,
        must_use=tuple(resolver.short_name(i) for i in must),
        may_buy=tuple(sorted(resolver.short_name(i) for i in set(query.could_buy) & usable)),
        hints=tuple(GOAL_HINTS[g] for g in goals if g in GOAL_HINTS),
        avoid_titles=tuple(on_screen[:AVOID_MAX]),
        substitution_rules=(TORTILLA_RULE.format(name=resolver.short_name(tortilla)),) if tortilla else (),
        blocked=blocked,
    )


def run_ideas(
    generator: IdeaGenerator, request: IdeaRequest, *, revise: bool, daily_reserve: int = 0
) -> tuple[IdeasRun, IdeasOutcome | None]:
    """One ideas call, its outcome turned into what the screen shows. Never raises an LLM error."""
    try:
        outcome = generator.generate(request, revise=revise, daily_reserve=daily_reserve)
    except (LLMWaitTooLongError, LLMRateLimitedError) as exc:
        retry = wait_seconds(exc.retry_after_s) if exc.retry_after_s is not None else 60
        return IdeasRun("partial", notes=[NOTE_WAITING], retry_after_s=retry, error_code=exc.code), None
    except LLMBudgetExceededError as exc:
        return IdeasRun("partial", notes=[NOTE_DAILY], error_code=exc.code), None
    except LLMConfigError as exc:
        return IdeasRun("partial", notes=[NOTE_NOT_SET_UP.format(reason=exc)], error_code=exc.code), None
    except LLMError as exc:
        log.warning("ideas call failed: %s", exc)
        return IdeasRun("partial", notes=[NOTE_FAILED], error_code=exc.code), None
    if not outcome.passed:
        return IdeasRun("partial", notes=[NOTE_FAILED], error_code="no_idea_passed"), outcome
    return IdeasRun("succeeded", created=list(outcome.created)), outcome
