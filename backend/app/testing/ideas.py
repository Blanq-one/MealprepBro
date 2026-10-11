"""Test helpers for ideas (step 2b.9): a task list that matches the idea's equipment and gives the active and
total minutes a test asks for, and steps whose timing matches it."""

from typing import Any

from app.domain.cook_schedule import APPLIANCES

TEMPS = {"oven": 425, "air_fryer": 400}


def task(
    component: str | None, equipment: str | None, on: int, off: int, temp: int | None = None
) -> dict[str, Any]:
    return {
        "component": component,
        "equipment": equipment,
        "hands_on_minutes": on,
        "hands_off_minutes": off,
        "appliance_temp_f": temp if temp is not None else TEMPS.get(equipment or ""),
    }


# chicken seared, rice simmered beside it, spinach stirred in at the end: 20 hands-on, ready in 30
DEFAULT_TASKS = [
    task(None, None, 5, 0),
    task("chicken", "stovetop", 8, 0),
    task("rice", "stovetop", 2, 18),
    task(None, None, 5, 0),
]


def idea_tasks(
    active: int = 20, total: int = 30, equipment: tuple[str, ...] | list[str] = ("stovetop",)
) -> list[dict[str, Any]]:
    """Tasks an idea's code-computed minutes come out of: `active` hands-on, ready in `total` (one appliance
    or none: exactly; several: each runs side by side after the prep). Every listed appliance has a task."""
    if (active, total, tuple(equipment)) == (20, 30, ("stovetop",)):
        return [dict(t) for t in DEFAULT_TASKS]
    appliances = [e for e in equipment if e in APPLIANCES]
    if not appliances:  # no-cook: the hands-on work, then any wait (chilling) as one shared task
        return [task(None, None, max(active, 1), max(total - active, 0))]
    tasks = [task(None, None, max(active - 2 * len(appliances), 1), 0)]
    for e in appliances:
        tasks.append(task(e, e, 2, max(total - active, 0)))
    return tasks
