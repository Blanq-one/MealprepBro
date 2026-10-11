"""Recipe timing for the cook-day schedule (step 2b.9, FLOW_SPEC §20): an idea's own task list, a seed's
tagged steps, or an estimate from untagged steps (V15); and a plan's batches as the scheduler sees them.

An idea always uses its tasks, also after its steps are written, so a plan's times never change when the
steps arrive (F31)."""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RecipeStep, RecipeVersion
from app.domain.cook_schedule import (
    DaySchedule,
    DishBatch,
    DishTiming,
    StepTiming,
    Task,
    fallback_timing,
    no_appliance,
    schedule_day,
    task_section,
    timing_from_steps,
    timing_from_tasks,
)
from app.planning.problem import CandidateRecipe


def tasks_from_json(rows: Iterable[Mapping[str, Any]]) -> tuple[Task, ...]:
    """`recipe_version.tasks` (an idea's PrepTask list, as saved) as scheduler tasks."""
    out = []
    for row in rows:
        component = row.get("component")
        equipment = row.get("equipment")
        hands_off = int(row.get("hands_off_minutes", 0))
        out.append(
            Task(
                component,
                equipment,
                int(row.get("hands_on_minutes", 0)),
                hands_off,
                row.get("appliance_temp_f"),
                task_section(component, equipment, hands_off),
            )
        )
    return tuple(out)


def step_timings(steps: Iterable[RecipeStep]) -> list[StepTiming]:
    return [
        StepTiming(
            s.section,
            s.duration_minutes,
            s.appliance_temp_f,
            s.component,
            s.equipment,
            s.hands_on_minutes,
            s.hands_off_minutes,
        )
        for s in steps
    ]


def version_timing(version: RecipeVersion, steps: Sequence[RecipeStep]) -> DishTiming:
    if version.tasks:
        return timing_from_tasks(tasks_from_json(version.tasks))
    if steps:
        return timing_from_steps(
            step_timings(steps),
            active_minutes=version.active_minutes,
            total_minutes=version.total_minutes,
            equipment=version.equipment,
        )
    return fallback_timing(
        version.active_minutes, version.total_minutes, no_cook=no_appliance(version.equipment)
    )


def load_timings(session: Session, versions: Iterable[RecipeVersion]) -> dict[int, DishTiming]:
    by_id = {v.id: v for v in versions}
    steps: dict[int, list[RecipeStep]] = defaultdict(list)
    if by_id:
        for step in session.scalars(
            select(RecipeStep)
            .where(RecipeStep.recipe_version_id.in_(sorted(by_id)))
            .order_by(RecipeStep.recipe_version_id, RecipeStep.position)
        ):
            steps[step.recipe_version_id].append(step)
    return {vid: version_timing(v, steps[vid]) for vid, v in by_id.items()}


def load_version_timings(session: Session, version_ids: Iterable[int]) -> dict[int, DishTiming]:
    ids = sorted(set(version_ids))
    if not ids:
        return {}
    return load_timings(session, session.scalars(select(RecipeVersion).where(RecipeVersion.id.in_(ids))))


def batch_key(version_id: int, portion_size: str) -> str:
    """Orders a day's batches the same way whatever order they come in."""
    return f"{version_id:010d}/{portion_size}"


def dish_batch(
    version_id: int, portion_size: str, *, title: str, timing: DishTiming, base_servings: int, portions: int
) -> DishBatch:
    return DishBatch(batch_key(version_id, portion_size), title, timing, base_servings, portions)


def planned_batch(recipe: CandidateRecipe, portion_size: str, portions: int) -> DishBatch:
    """A batch of a candidate recipe as the scheduler sees it."""
    return dish_batch(
        recipe.version_id,
        portion_size,
        title=recipe.title,
        timing=recipe.schedule_timing,
        base_servings=recipe.base_servings,
        portions=portions,
    )


def day_schedules(batches: Iterable[tuple[date, DishBatch]]) -> dict[date, DaySchedule]:
    """Each cook day's schedule for (cook day, batch) pairs."""
    by_day: dict[date, list[DishBatch]] = defaultdict(list)
    for day, batch in batches:
        by_day[day].append(batch)
    return {day: schedule_day(items) for day, items in sorted(by_day.items())}
