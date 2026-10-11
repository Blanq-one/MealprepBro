"""Pass 1 of two-stage generation (E15, FLOW_SPEC §13.5): one call returns 5–8 ideas (ingredients and amounts,
a one-line method, equipment and times; no steps). Used by meal now here and by meal prep, swap and grocery
advice from step 2b.5.

  size      code picks the count: the largest from 8 down to 5 whose prompt estimate + count × 360 + 300
            (reasoning) fits in 95% of the minute's limit; if even 5 don't fit, no call is made;
  check     every recipe check except the step checks (planning/recipe_validator.validate_idea), plus the
            request's own: the meal, the mood, the time limits, this week's used-up caps, complete nutrition;
  save      a passing idea becomes a recipe version with `steps_status = pending` and no steps (§13.4), so its
            numbers are code-computed and it ranks and plans like any saved recipe;
  revise    only when no idea in a batch passes: one `idea_revision/1` call with at most 3 failed ideas.
A failing idea is dropped, with its reasons logged on the call (CLAUDE.md rule 5).
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LlmCall, Recipe, RecipeIngredient, RecipeVersion
from app.domain.cook_time import MOOD_ORDER
from app.domain.enums import Equipment, MealSlot, RecipeMood, RecipeOrigin
from app.llm.errors import LLMError, LLMOutputError
from app.llm.prompts import idea_revision, recipe_ideas
from app.llm.prompts.common import IdeaContext
from app.llm.structured import LLMRunContext, StructuredSpec
from app.planning.recipe_validator import ValidatedIdea, validate_idea
from app.planning.resolver import IngredientResolver
from app.schemas.llm_recipe import RecipeIdea, RecipeIdeaBatch
from app.services.calculations import LineInput, calculate

PER_IDEA_TOKENS = 360  # measured in the 2b.3b live test: 8 ideas took 3,117 completion tokens (330 planned)
REASONING_TOKENS = 300
MAX_IDEAS = 8
MIN_IDEAS = 5
COMPLETION_MARGIN = 1.25  # room above the expected completion, within the minute's budget
MAX_REVISED = 3
PENDING = "pending"  # recipe_version.steps_status of an idea whose steps are written on first open
_Q3 = Decimal("0.001")


class IdeasDontFitError(LLMError):
    """Even 5 ideas don't fit one call under the minute's limit: no call is made."""

    code = "llm_ideas_dont_fit"


@dataclass(frozen=True)
class IdeaRequest:
    """What one ideas call asks for, resolved by the caller (meal now, meal prep, swap, grocery advice)."""

    slot: MealSlot
    mood: RecipeMood
    base_servings: int
    equipment: frozenset[Equipment]
    vocabulary: tuple[str, ...]  # short names
    never_use: tuple[str, ...]
    max_active_minutes: int
    max_total_minutes: int | None = None  # Quick
    kcal_per_portion: int | None = None
    must_use: tuple[str, ...] = ()
    may_buy: tuple[str, ...] = ()
    hints: tuple[str, ...] = ()
    use_up: tuple[str, ...] = ()
    avoid_titles: tuple[str, ...] = ()
    substitution_rules: tuple[str, ...] = ()
    # ingredients a frequency cap has used up this calendar week: label of the cap per ingredient id
    blocked: Mapping[int, str] = field(default_factory=dict)

    def context(self, count: int) -> IdeaContext:
        return IdeaContext(
            slot=self.slot.value,
            mood=self.mood.value,
            count=count,
            max_active_minutes=self.max_active_minutes,
            base_servings=self.base_servings,
            equipment=tuple(sorted(e.value for e in self.equipment)),
            vocabulary=self.vocabulary,
            never_use=self.never_use,
            max_total_minutes=self.max_total_minutes,
            kcal_per_portion=self.kcal_per_portion,
            must_use=self.must_use,
            may_buy=self.may_buy,
            hints=self.hints,
            use_up=self.use_up,
            avoid_titles=self.avoid_titles,
            substitution_rules=self.substitution_rules,
        )


@dataclass(frozen=True)
class CallSize:
    count: int
    max_completion_tokens: int
    prompt_tokens: int


def size_call(prompt_tokens: int, budget: int) -> CallSize | None:
    """The largest count from 8 down to 5 that fits: prompt + count × 360 + 300 within `budget` (95% of the
    minute's limit). The maximum completion gets a 25% margin over that, still within the budget."""
    for count in range(MAX_IDEAS, MIN_IDEAS - 1, -1):
        expected = count * PER_IDEA_TOKENS + REASONING_TOKENS
        if prompt_tokens + expected <= budget:
            room = budget - prompt_tokens
            return CallSize(count, min(room, math.ceil(expected * COMPLETION_MARGIN)), prompt_tokens)
    return None


@dataclass
class IdeasOutcome:
    created: list[int] = field(default_factory=list)  # versions this pass saved, in idea order
    passed: list[int] = field(default_factory=list)  # every passing idea (new, or identical to a saved one)
    dropped: dict[str, list[str]] = field(default_factory=dict)  # title -> why
    asked: int = 0
    revised: bool = False


def salvage_ideas(payload: Any) -> RecipeIdeaBatch | None:
    """From a batch the provider rejected, or that one bad idea broke, the ideas that validate on their own
    (the rest are dropped and logged, as ideas that fail the checks are)."""
    items = payload.get("ideas") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None
    kept = []
    for item in items[:MAX_IDEAS]:
        try:
            kept.append(RecipeIdea.model_validate(item))
        except ValidationError:
            continue
    return RecipeIdeaBatch(ideas=kept) if kept else None


def idea_hash(validated: ValidatedIdea) -> str:
    """An idea's content hash (title, lines, servings): unchanged when its steps are written later (§13.4)."""
    idea = validated.idea
    payload = {
        "title": idea.title.strip().lower(),
        "lines": [[ln.ingredient_id, str(ln.quantity), ln.unit] for ln in validated.lines],
        "base_servings": idea.base_servings,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class IdeaGenerator:
    """Talks to the LLM for one request. Everything worth keeping is saved (CLAUDE.md rule 7)."""

    def __init__(
        self, session: Session, user_id: int, llm: LLMRunContext, resolver: IngredientResolver | None = None
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.llm = llm.for_ideas()  # LLM_IDEAS_MODEL when set (P5)
        self.resolver = resolver or IngredientResolver(session, user_id)

    # ---- size ----
    def size(self, req: IdeaRequest) -> CallSize:
        messages = recipe_ideas.build_messages(req.context(MAX_IDEAS))
        prompt = self.llm.prompt_estimate(recipe_ideas.PURPOSE, messages, RecipeIdeaBatch)
        size = size_call(prompt, self.llm.pacer.call_budget())
        if size is None:
            raise IdeasDontFitError(
                f"even {MIN_IDEAS} ideas don't fit one call: the prompt is about {prompt:,} tokens and the "
                f"minute's budget {self.llm.pacer.call_budget():,}",
                detail={"prompt_tokens": prompt, "budget": self.llm.pacer.call_budget()},
            )
        return size

    # ---- checks ----
    def check(self, idea: RecipeIdea, req: IdeaRequest) -> tuple[ValidatedIdea | None, list[str]]:
        validated, errors = validate_idea(idea, self.resolver, req.equipment)
        if req.slot not in idea.meal_slots:
            errors.append(f"meal_slots must include '{req.slot.value}'")
        if MOOD_ORDER[idea.mood] > MOOD_ORDER[req.mood]:
            errors.append(f"mood must be {req.mood.value} or simpler")
        if idea.active_minutes > req.max_active_minutes:
            errors.append(f"active_minutes must be at most {req.max_active_minutes}")
        if req.max_total_minutes is not None and idea.total_minutes > req.max_total_minutes:
            errors.append(f"total_minutes must be at most {req.max_total_minutes}")
        if validated is not None:
            for line in validated.lines:
                if (label := req.blocked.get(line.ingredient_id)) is not None:
                    errors.append(
                        f"'{line.written_name}': {label}, this week's allowance is used up; leave it out"
                    )
            calc = calculate(
                self.session,
                [
                    LineInput(ln.ingredient_id, ln.authored_quantity, ln.authored_unit, ln.optional)
                    for ln in validated.lines
                ],
                idea.base_servings,
            )
            if not calc.nutrition_complete:
                errors.append(
                    "its nutrition can't be computed ("
                    + "; ".join(calc.incomplete_reasons)
                    + "); use other listed ingredients"
                )
        if errors:
            return None, list(dict.fromkeys(errors))
        return validated, []

    # ---- generation ----
    def generate(self, req: IdeaRequest, *, revise: bool = True, daily_reserve: int = 0) -> IdeasOutcome:
        """One ideas call (and, when no idea passes and `revise`, one revision). Raises the LLM's errors (rate
        waits, the daily guard, invalid output after the capped attempts) for the caller to turn into a note;
        ideas saved before an error stay saved."""
        size = self.size(req)
        spec = StructuredSpec(
            purpose=recipe_ideas.PURPOSE,
            prompt_version=recipe_ideas.PROMPT_VERSION,
            messages=recipe_ideas.build_messages(req.context(size.count)),
            response_model=RecipeIdeaBatch,
            max_completion_tokens=size.max_completion_tokens,
            daily_reserve=daily_reserve,
            salvage=salvage_ideas,
        )
        result = self.llm.generate(spec)
        outcome = IdeasOutcome(asked=size.count)
        failed: list[tuple[RecipeIdea, list[str]]] = []
        for idea in result.value.ideas:
            validated, errors = self.check(idea, req)
            if validated is None:
                outcome.dropped[idea.title] = errors
                failed.append((idea, errors))
                continue
            self._keep(outcome, validated, result.final_call_id, recipe_ideas.PROMPT_VERSION)
        self._note(
            result.final_call_id,
            outcome.dropped,
            rate=(size.count, len(result.value.ideas), len(outcome.passed)),
        )
        if not outcome.passed and failed and revise:
            outcome.revised = True
            self._revise(req, failed[:MAX_REVISED], result.final_call_id, outcome, daily_reserve)
        return outcome

    def _revise(
        self,
        req: IdeaRequest,
        failed: list[tuple[RecipeIdea, list[str]]],
        parent_id: int,
        outcome: IdeasOutcome,
        daily_reserve: int,
    ) -> None:
        holder: dict[int, ValidatedIdea] = {}

        def domain(batch: RecipeIdeaBatch) -> list[str]:
            problems: list[str] = []
            holder.clear()
            for n, idea in enumerate(batch.ideas):
                validated, errors = self.check(idea, req)
                if validated is not None:
                    holder[n] = validated
                else:
                    problems += [f"{idea.title}: {e}" for e in errors]
            return [] if holder else problems

        messages = idea_revision.build_messages(
            req.context(len(failed)), [(idea.model_dump_json(), errors) for idea, errors in failed]
        )
        prompt = self.llm.prompt_estimate(idea_revision.PURPOSE, messages, RecipeIdeaBatch)
        expected = len(failed) * PER_IDEA_TOKENS + REASONING_TOKENS
        room = self.llm.pacer.call_budget() - prompt
        if room < expected:  # the revision wouldn't fit one call: keep the reasons and stop
            return
        spec = StructuredSpec(
            purpose=idea_revision.PURPOSE,
            prompt_version=idea_revision.PROMPT_VERSION,
            messages=messages,
            response_model=RecipeIdeaBatch,
            domain_check=domain,
            max_completion_tokens=min(room, math.ceil(expected * COMPLETION_MARGIN)),
            daily_reserve=daily_reserve,
        )
        try:
            result = self.llm.generate(spec)
        except LLMOutputError as exc:
            for idea, errors in failed:
                outcome.dropped[idea.title] = list(exc.detail.get("errors", errors))
            return
        first = self.session.get(LlmCall, result.call_ids[0])
        if first is not None and first.parent_call_id is None:
            first.parent_call_id = parent_id
        kept_before = len(outcome.passed)
        for n in sorted(holder):
            self._keep(outcome, holder[n], result.final_call_id, idea_revision.PROMPT_VERSION)
        self._note(
            result.final_call_id,
            {},
            rate=(len(failed), len(result.value.ideas), len(outcome.passed) - kept_before),
        )

    def _keep(
        self, outcome: IdeasOutcome, validated: ValidatedIdea, call_id: int, prompt_version: str
    ) -> None:
        version_id, created = self._persist(validated, call_id, prompt_version)
        if version_id in outcome.passed:
            return
        outcome.passed.append(version_id)
        if created:
            outcome.created.append(version_id)

    def _note(self, call_id: int, issues: dict[str, list[str]], *, rate: tuple[int, int, int]) -> None:
        """On the call's log row: why ideas were dropped, and the pass rate (P7): ideas asked for, returned
        and kept (passed the checks; one identical to a saved idea counts too)."""
        row = self.session.get(LlmCall, call_id)
        if row is None:
            return
        detail = dict(row.error_detail or {})
        asked, returned, kept = rate
        detail["ideas"] = {
            "asked": asked,
            "returned": returned,
            "kept": kept,
            "pass_rate": round(kept / asked, 3) if asked else None,
        }
        if issues:
            detail["idea_issues"] = issues
        if self.resolver.unresolved:
            detail["unresolved_ingredients"] = sorted(self.resolver.unresolved)
        row.error_detail = detail or None
        self.session.flush()

    def _persist(self, validated: ValidatedIdea, call_id: int, prompt_version: str) -> tuple[int, bool]:
        digest = idea_hash(validated)
        existing = self.session.scalars(
            select(RecipeVersion.id)
            .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
            .where(Recipe.user_id == self.user_id, RecipeVersion.content_hash == digest)
        ).first()
        if existing is not None:
            return existing, False  # dedupe: the same idea again
        idea = validated.idea
        recipe = Recipe(user_id=self.user_id, title=idea.title, origin=RecipeOrigin.LLM.value)
        self.session.add(recipe)
        self.session.flush()
        substitutions = [
            f"{ln.substituted_from} → {ln.name}" for ln in validated.lines if ln.substituted_from
        ]
        version = RecipeVersion(
            recipe_id=recipe.id,
            version_number=1,
            created_by="llm",
            is_draft=False,
            change_summary=("Substituted: " + "; ".join(substitutions)) if substitutions else None,
            title=idea.title,
            description=idea.method,  # the one-line method (§13.4: no other column needed)
            meal_slots=[s.value for s in idea.meal_slots],
            mood=idea.mood.value,
            cuisine=None,
            flavor_tags=[],
            base_servings=idea.base_servings,
            active_minutes=idea.active_minutes,
            total_minutes=idea.total_minutes,
            equipment=[e.value for e in idea.equipment],
            freezer_friendly=idea.freezer_friendly,
            content_hash=digest,
            prompt_version=prompt_version,
            source_llm_call_id=call_id,
            generation_run_id=self.llm.run_id,
            steps_status=PENDING,
        )
        self.session.add(version)
        self.session.flush()
        for position, ln in enumerate(validated.lines, start=1):
            self.session.add(
                RecipeIngredient(
                    recipe_version_id=version.id,
                    position=position,
                    ingredient_id=ln.ingredient_id,
                    quantity=ln.quantity.quantize(_Q3, ROUND_HALF_UP),
                    unit=ln.unit,
                    authored_quantity=ln.authored_quantity.quantize(_Q3, ROUND_HALF_UP),
                    authored_unit=ln.authored_unit,
                    preparation=None,
                    role=ln.role,
                    component=None,
                    is_optional=False,
                )
            )
        self.session.flush()
        recipe.default_version_id = version.id
        self.session.flush()
        return version.id, True
