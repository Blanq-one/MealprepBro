"""Pass 2 of two-stage generation (E19, FLOW_SPEC §13.5, change F19): an idea's steps are written the first
time it is opened, once, and saved with it.

  * the prompt carries only the saved idea (title, method, mood, servings, minutes, equipment, its lines in
    short names with the stored amounts);
  * idea + steps are validated as one GeneratedRecipe, so every step check runs unchanged (prep and portioning
    steps, each section's equipment in the idea's equipment, oven and air-fryer temperatures, every
    ingredient a step uses on the list, doneness checks that resolve, the prose filter), then the food-safety
    lines are added; a failure retries with the errors (rule 5);
  * the steps are inserted in the same transaction that sets `steps_status` from pending to NULL; nothing else
    on the version changes (its lines, and so its numbers, can't: the steps can't touch them);
  * one call per recipe at a time: a second request for the same idea waits for the first one's result (a lock
    in this process, and the running `recipe_steps` run for other processes).
Seed recipes, Phase 1 recipes and anything saved with steps never call it.
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GenerationRun, RecipeIngredient, RecipeStep, RecipeVersion
from app.domain.enums import Equipment, IngredientRole, MealSlot, RecipeMood
from app.llm.errors import LLMBudgetExceededError, LLMError, LLMRateLimitedError, LLMWaitTooLongError
from app.llm.pacing import Clock
from app.llm.prompts import recipe_steps
from app.llm.prompts.recipe_steps import StepsContext
from app.llm.structured import LLMRunContext, StructuredSpec
from app.planning.recipe_validator import StepScanner, ValidatedRecipe, validate_generated
from app.planning.resolver import IngredientResolver
from app.schemas.llm_recipe import IdeaIngredient, LLMUnit, RecipeIdea, RecipeSteps, idea_as_recipe

PURPOSE = recipe_steps.PURPOSE
STEPS_MAX_COMPLETION = 1600  # about 600 of steps and 300 of reasoning, with room (§15.1)
POLL_SECONDS = 1.0
STALE_AFTER = timedelta(seconds=330)  # a steps run older than this was cut off with its request

StepsStatus = Literal["ready", "waiting", "failed", "daily"]


@dataclass
class StepsOutcome:
    status: StepsStatus
    calls: int = 0
    run_id: int | None = None
    retry_after_s: float | None = None
    error: LLMError | None = None


_LOCKS: dict[int, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


@contextmanager
def _one_at_a_time(version_id: int) -> Iterator[None]:
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(version_id, threading.Lock())
    with lock:
        yield


def steps_running(session: Session, user_id: int, version_id: int | None = None) -> GenerationRun | None:
    """A steps call for you that is running or waiting (the background batch yields to it, §14)."""
    query = select(GenerationRun).where(
        GenerationRun.user_id == user_id,
        GenerationRun.purpose == PURPOSE,
        GenerationRun.status == "running",
        GenerationRun.created_at >= datetime.now(UTC) - STALE_AFTER,
    )
    if version_id is not None:
        query = query.where(GenerationRun.constraints["version_id"].as_integer() == version_id)
    return session.scalars(query.order_by(GenerationRun.id.desc())).first()


def _unit(authored: str) -> LLMUnit | None:
    try:
        return LLMUnit(authored)
    except ValueError:
        return None


def idea_of(version: RecipeVersion, rows: list[RecipeIngredient], resolver: IngredientResolver) -> RecipeIdea:
    """The saved idea, as the steps prompt and the checks see it: its lines in short names with their stored
    amounts (the authored unit when the LLM may use it, else the base unit)."""
    ingredients = []
    for row in rows:
        unit = _unit(row.authored_unit)
        quantity = row.authored_quantity if unit is not None else row.quantity
        if unit is None:
            unit = LLMUnit(row.unit)  # g / ml / count
        ingredients.append(
            IdeaIngredient(
                name=resolver.short_name(row.ingredient_id),
                quantity=float(quantity),
                unit=unit,
                role=IngredientRole(row.role),
            )
        )
    return RecipeIdea(
        title=version.title,
        method=version.description,
        meal_slots=[MealSlot(s) for s in version.meal_slots],
        mood=RecipeMood(version.mood),
        base_servings=version.base_servings,
        active_minutes=version.active_minutes,
        total_minutes=version.total_minutes,
        equipment=[Equipment(e) for e in version.equipment],
        freezer_friendly=version.freezer_friendly,
        ingredients=ingredients,
    )


def _amount(item: IdeaIngredient) -> str:
    return f"{item.name} {Decimal(str(item.quantity)).normalize():f} {item.unit.value}"


class StepsWriter:
    """Writes one idea's steps. `llm(run)` builds the LLM context for the run (its deadline and wait hook)."""

    def __init__(
        self,
        session: Session,
        user_id: int,
        llm: Callable[[GenerationRun], LLMRunContext],
        *,
        clock: Clock,
        checkpoint: Callable[[], None] = lambda: None,
        on_stage: Callable[[str], None] = lambda stage: None,
        max_poll_s: float = 120.0,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.llm = llm
        self.clock = clock
        self.checkpoint = checkpoint
        self.on_stage = on_stage
        self.max_poll_s = max_poll_s

    def write(self, version_id: int) -> StepsOutcome:
        with _one_at_a_time(version_id):
            version = self._version(version_id)
            if version.steps_status is None:
                return StepsOutcome(
                    "ready"
                )  # seed, Phase 1, saved, or written by the request before this one
            other = steps_running(self.session, self.user_id, version_id)
            if other is not None:  # another process is writing them: wait for its result
                return self._wait_for(other.id, version_id)
            return self._write(version)

    def _version(self, version_id: int) -> RecipeVersion:
        self.session.expire_all()
        version = self.session.get(RecipeVersion, version_id)
        assert version is not None
        return version

    def _wait_for(self, run_id: int, version_id: int) -> StepsOutcome:
        self.on_stage("writing_steps")
        waited = 0.0
        while waited < self.max_poll_s:
            self.clock.sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            if self._version(version_id).steps_status is None:
                return StepsOutcome("ready", run_id=run_id)
            run = self.session.get(GenerationRun, run_id)
            if run is None or run.status != "running":
                break
        return StepsOutcome("failed", run_id=run_id)

    def _write(self, version: RecipeVersion) -> StepsOutcome:
        run = GenerationRun(
            user_id=self.user_id,
            purpose=PURPOSE,
            status="running",
            started_at=datetime.now(UTC),
            constraints={"version_id": version.id},
            progress={"stage": "writing_steps"},
        )
        self.session.add(run)
        self.session.flush()
        self.checkpoint()  # other requests see the call is running
        ctx = self.llm(run)
        resolver = IngredientResolver(self.session, self.user_id)
        scanner = StepScanner(resolver)
        rows = list(
            self.session.scalars(
                select(RecipeIngredient)
                .where(RecipeIngredient.recipe_version_id == version.id)
                .order_by(RecipeIngredient.position)
            )
        )
        idea = idea_of(version, rows, resolver)
        stored = [row.ingredient_id for row in rows]
        holder: dict[str, ValidatedRecipe] = {}

        def domain(out: RecipeSteps) -> list[str]:
            self.on_stage("checking")
            try:
                recipe = idea_as_recipe(idea, out.steps)
            except ValidationError as exc:
                return [str(e["msg"]).removeprefix("Value error, ") for e in exc.errors()]
            validated, errors = validate_generated(recipe, resolver, scanner, frozenset(idea.equipment))
            if validated is None:
                return errors
            if [ln.ingredient_id for ln in validated.lines] != stored:  # never another ingredient
                return ["the ingredients changed; use exactly the listed ingredients"]
            holder["ok"] = validated
            return []

        messages = recipe_steps.build_messages(
            StepsContext(
                title=idea.title,
                method=idea.method,
                mood=idea.mood.value,
                base_servings=idea.base_servings,
                active_minutes=idea.active_minutes,
                total_minutes=idea.total_minutes,
                equipment=tuple(e.value for e in idea.equipment),
                ingredients=[_amount(i) for i in idea.ingredients],
            )
        )
        prompt = ctx.prompt_estimate(PURPOSE, messages, RecipeSteps)
        spec = StructuredSpec(
            purpose=PURPOSE,
            prompt_version=recipe_steps.PROMPT_VERSION,
            messages=messages,
            response_model=RecipeSteps,
            domain_check=domain,
            max_completion_tokens=max(256, min(STEPS_MAX_COMPLETION, ctx.pacer.call_budget() - prompt)),
        )
        self.on_stage("writing_steps")
        try:
            ctx.generate(spec)
        except (LLMWaitTooLongError, LLMRateLimitedError) as exc:
            return self._end(run, StepsOutcome("waiting", retry_after_s=exc.retry_after_s, error=exc))
        except LLMBudgetExceededError as exc:
            return self._end(run, StepsOutcome("daily", error=exc))
        except LLMError as exc:
            return self._end(run, StepsOutcome("failed", error=exc))
        self._save(version, holder["ok"])
        return self._end(run, StepsOutcome("ready"))

    def _save(self, version: RecipeVersion, validated: ValidatedRecipe) -> None:
        """Write-once (F19): the steps and steps_status together, nothing else on the version."""
        for position, step in enumerate(validated.steps, start=1):
            self.session.add(
                RecipeStep(
                    recipe_version_id=version.id,
                    position=position,
                    section=step.section,
                    text=step.text,
                    duration_minutes=step.duration_minutes,
                    appliance_temp_f=step.appliance_temp_f,
                    doneness_check_ingredient_id=step.doneness_check_ingredient_id,
                )
            )
        version.steps_status = None
        self.session.flush()

    def _end(self, run: GenerationRun, outcome: StepsOutcome) -> StepsOutcome:
        run.status = "succeeded" if outcome.status == "ready" else "failed"
        run.finished_at = datetime.now(UTC)
        if outcome.error is not None:
            run.error = {"code": outcome.error.code, "detail": str(outcome.error)}
        outcome.run_id, outcome.calls = run.id, run.llm_call_count
        self.session.flush()
        self.checkpoint()
        return outcome
