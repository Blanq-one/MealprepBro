"""The candidate pool (deliverable 10): seed drafts and saved versions first (0 LLM calls), then gap analysis,
then batch generation only for uncovered slots, a targeted revision call for each invalid recipe, dedupe,
and persistence with provenance (CLAUDE.md rule 7: every generated recipe is saved and reused).
"""

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LlmCall, Recipe, RecipeIngredient, RecipeStep, RecipeVersion
from app.domain.cook_time import MOOD_MAX_ACTIVE_MINUTES, MOOD_ORDER
from app.domain.enums import MealSlot, RecipeMood, RecipeOrigin
from app.domain.exclusions import ExclusionStatus
from app.llm.errors import LLMOutputError, LLMTruncatedError
from app.llm.prompts import candidate_generation, recipe_revision
from app.llm.prompts.common import GenerationContext
from app.llm.structured import LLMRunContext, StructuredSpec
from app.planning.problem import PlanningProblem
from app.planning.recipe_validator import StepScanner, ValidatedRecipe, validate_generated
from app.planning.resolver import IngredientResolver
from app.schemas.constraints import VARIETY_CAPPED_SLOTS
from app.schemas.llm_recipe import GeneratedRecipe, GeneratedRecipeBatch

MAX_PER_CALL = 3  # 2–3 recipes per call keeps responses inside Groq's 8K tokens/minute
BASE_SERVINGS = {MealSlot.LUNCH: 4, MealSlot.DINNER: 4, MealSlot.BREAKFAST: 4}
TORTILLA_RULE = "use '{name}' wherever a recipe would call for chapati or roti"


@dataclass(frozen=True)
class Gap:
    slot: MealSlot
    count: int  # recipes to generate
    reason: str


def gap_analysis(problem: PlanningProblem) -> list[Gap]:
    """Only slots without enough candidates go to the LLM. A meal slot needs enough distinct recipes for the
    weekly variety cap; desserts, snacks and drinks need one."""
    c = problem.constraints
    gaps = []
    for slot in sorted({s for d in c.days for s in d.slots}, key=lambda s: list(MealSlot).index(s)):
        days = sum(1 for d in c.days if slot in d.slots)
        have = sum(1 for r in problem.candidates if slot in r.meal_slots)
        need = math.ceil(days / c.max_portions_per_recipe) if slot in VARIETY_CAPPED_SLOTS else 1
        if have < need:
            gaps.append(
                Gap(slot, min(MAX_PER_CALL, max(2, need - have + 1)), f"{have} of {need} recipes needed")
            )
    return gaps


def content_hash(validated: ValidatedRecipe) -> str:
    r = validated.recipe
    payload = {
        "title": r.title.strip().lower(),
        "lines": [[ln.ingredient_id, str(ln.quantity), ln.unit] for ln in validated.lines],
        "steps": [s.text.strip() for s in validated.steps],
        "base_servings": r.base_servings,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class CandidateGenerator:
    """Talks to the LLM for one run. Stateless across runs: everything worth keeping is in the database."""

    def __init__(self, session: Session, user_id: int, llm: LLMRunContext) -> None:
        self.session = session
        self.user_id = user_id
        self.llm = llm
        self.resolver = IngredientResolver(session, user_id)
        self.scanner = StepScanner(self.resolver)
        self.created: list[int] = []
        self.dropped: list[tuple[str, list[str]]] = []

    # ---- context ----
    def context(self, problem: PlanningProblem, gap: Gap) -> GenerationContext:
        c = problem.constraints
        statuses = self.resolver.statuses
        never_favored = {i for cap in c.frequency_caps if cap.never_favor for i in cap.member_ingredient_ids}
        vocabulary = sorted(
            d.name
            for i, d in self.resolver.data.items()
            if statuses[i].status is ExclusionStatus.ALLOWED
            and i not in never_favored
            and d.slug != "chapati"
        )
        never_use = ["beef and anything made from beef (broth, stock, tallow, bouillon, bovine gelatin)"]
        never_use += sorted(
            self.resolver.data[i].name for i, s in statuses.items() if s.status is not ExclusionStatus.ALLOWED
        )
        cook_days = [d for d in c.days if d.is_cook_day]
        mood = min((d.mood for d in cook_days), key=lambda m: MOOD_ORDER[m], default=RecipeMood.SIMPLE)
        minutes = min(
            MOOD_MAX_ACTIVE_MINUTES[mood], max((d.cook_minutes_available for d in cook_days), default=30)
        )
        use_up = []
        for plan in problem.ingredients.values():
            for lot in plan.lots:
                if lot.opened or (lot.expires_on is not None and lot.expires_on <= c.week_end):
                    tag = "open package" if lot.opened else f"expires {lot.expires_on}"
                    use_up.append(f"{plan.name} (about {lot.quantity:.0f} {plan.planning_unit}, {tag})")
        tortilla = next(
            (d.name for d in self.resolver.data.values() if d.slug == "flour-tortilla-small"), None
        )
        return GenerationContext(
            slot=gap.slot.value,
            mood=mood.value,
            count=gap.count,
            max_active_minutes=minutes,
            kcal_per_portion=c.slot_target(gap.slot).kcal,
            base_servings=BASE_SERVINGS.get(gap.slot, 2),
            equipment=tuple(sorted(e.value for e in c.equipment)),
            vocabulary=tuple(vocabulary),
            never_use=tuple(never_use),
            use_up=tuple(sorted(use_up)),
            avoid_titles=tuple(sorted(r.title for r in problem.candidates if gap.slot in r.meal_slots)),
            substitution_rules=(TORTILLA_RULE.format(name=tortilla),) if tortilla else (),
        )

    # ---- validation (also the revision call's domain hook) ----
    def check(
        self, recipe: GeneratedRecipe, gap: Gap, ctx: GenerationContext
    ) -> tuple[ValidatedRecipe | None, list[str]]:
        validated, errors = validate_generated(recipe, self.resolver, self.scanner, frozenset(self.equipment))
        if gap.slot not in recipe.meal_slots:
            errors.append(f"meal_slots must include '{gap.slot.value}'")
        if MOOD_ORDER[recipe.mood] > MOOD_ORDER[RecipeMood(ctx.mood)]:
            errors.append(f"mood must be {ctx.mood} or simpler")
        if recipe.active_minutes > ctx.max_active_minutes:
            errors.append(f"active_minutes must be at most {ctx.max_active_minutes}")
        return (validated if not errors else None), errors

    # ---- generation ----
    def generate(self, problem: PlanningProblem, gaps: Sequence[Gap]) -> list[int]:
        self.equipment = problem.constraints.equipment
        new_ids: list[int] = []
        for gap in gaps:
            new_ids.extend(self._generate_gap(problem, gap))
        return new_ids

    def _generate_gap(self, problem: PlanningProblem, gap: Gap) -> list[int]:
        ctx = self.context(problem, gap)
        count = gap.count
        while True:
            spec = StructuredSpec(
                purpose=candidate_generation.PURPOSE,
                prompt_version=candidate_generation.PROMPT_VERSION,
                messages=candidate_generation.build_messages(
                    GenerationContext(**{**ctx.__dict__, "count": count})
                ),
                response_model=GeneratedRecipeBatch,
                raise_on_truncation=count > 1,
            )
            try:
                result = self.llm.generate(spec)
                break
            except LLMTruncatedError:
                count = max(1, count // 2)  # halve the batch and try again
        ids: list[int] = []
        issues: dict[str, list[str]] = {}
        for recipe in result.value.recipes:
            validated, errors = self.check(recipe, gap, ctx)
            call_id = result.final_call_id
            if validated is None:
                issues[recipe.title] = errors
                validated, call_id = self._revise(recipe, errors, gap, ctx, result.final_call_id)
            if validated is not None:
                ids.append(
                    self._persist(
                        validated,
                        call_id,
                        recipe_revision.PROMPT_VERSION
                        if call_id != result.final_call_id
                        else candidate_generation.PROMPT_VERSION,
                    )
                )
        self._note_issues(result.final_call_id, issues)
        return ids

    def _revise(
        self, recipe: GeneratedRecipe, errors: list[str], gap: Gap, ctx: GenerationContext, parent_id: int
    ) -> tuple[ValidatedRecipe | None, int]:
        holder: dict[str, ValidatedRecipe] = {}

        def domain(candidate: GeneratedRecipe) -> list[str]:
            validated, problems = self.check(candidate, gap, ctx)
            if validated is not None:
                holder["ok"] = validated
            return problems

        spec = StructuredSpec(
            purpose=recipe_revision.PURPOSE,
            prompt_version=recipe_revision.PROMPT_VERSION,
            messages=recipe_revision.build_messages(ctx, recipe.model_dump_json(), errors),
            response_model=GeneratedRecipe,
            domain_check=domain,
        )
        try:
            result = self.llm.generate(spec)
        except LLMOutputError as exc:
            self.dropped.append((recipe.title, list(exc.detail.get("errors", errors))))
            return None, parent_id
        first = self.session.get(LlmCall, result.call_ids[0])
        if first is not None and first.parent_call_id is None:
            first.parent_call_id = parent_id
        return holder.get("ok"), result.final_call_id

    def _note_issues(self, call_id: int, issues: dict[str, list[str]]) -> None:
        row = self.session.get(LlmCall, call_id)
        if row is None:
            return
        detail = dict(row.error_detail or {})
        if issues:
            detail["recipe_issues"] = issues
        if self.resolver.unresolved:
            detail["unresolved_ingredients"] = sorted(self.resolver.unresolved)
        row.error_detail = detail or None
        self.session.flush()

    def _persist(self, validated: ValidatedRecipe, call_id: int, prompt_version: str) -> int:
        digest = content_hash(validated)
        existing = self.session.scalars(
            select(RecipeVersion.id)
            .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
            .where(Recipe.user_id == self.user_id, RecipeVersion.content_hash == digest)
        ).first()
        if existing is not None:
            return existing  # dedupe: the same recipe again
        r = validated.recipe
        recipe = Recipe(user_id=self.user_id, title=r.title, origin=RecipeOrigin.LLM.value)
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
            title=r.title,
            description=r.description,
            meal_slots=[s.value for s in r.meal_slots],
            mood=r.mood.value,
            cuisine=r.cuisine,
            flavor_tags=list(r.flavor_tags),
            base_servings=r.base_servings,
            active_minutes=r.active_minutes,
            total_minutes=r.total_minutes,
            equipment=[e.value for e in r.equipment],
            freezer_friendly=r.freezer_friendly,
            content_hash=digest,
            prompt_version=prompt_version,
            source_llm_call_id=call_id,
            generation_run_id=self.llm.run_id,
        )
        self.session.add(version)
        self.session.flush()
        q3 = Decimal("0.001")
        for position, ln in enumerate(validated.lines, start=1):
            self.session.add(
                RecipeIngredient(
                    recipe_version_id=version.id,
                    position=position,
                    ingredient_id=ln.ingredient_id,
                    quantity=ln.quantity.quantize(q3, ROUND_HALF_UP),
                    unit=ln.unit,
                    authored_quantity=ln.authored_quantity.quantize(q3, ROUND_HALF_UP),
                    authored_unit=ln.authored_unit,
                    preparation=ln.preparation,
                    role=ln.role,
                    component=ln.component,
                    is_optional=ln.optional,
                )
            )
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
        self.session.flush()
        recipe.default_version_id = version.id
        self.session.flush()
        self.created.append(version.id)
        return version.id
