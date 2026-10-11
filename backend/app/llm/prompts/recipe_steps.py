"""Pass 2 of two-stage generation (FLOW_SPEC §13.5): the steps for one saved idea, written the first time it
is opened. The prompt carries only the idea; its ingredients are fixed, so there is no vocabulary and no
never-use list."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.llm.client import Message
from app.llm.prompts.common import STEP_RULES, equipment_line

PROMPT_VERSION = "recipe_steps/2"  # /2: each step's timing, matching the idea's tasks (2b.9)
PURPOSE = "recipe_steps"


@dataclass(frozen=True)
class StepsContext:
    title: str
    method: str
    mood: str
    base_servings: int
    active_minutes: int
    total_minutes: int
    equipment: tuple[str, ...]
    ingredients: Sequence[str]  # "chicken thigh 680 g", in short names with the stored amounts
    tasks: Sequence[str] = ()  # "rice (stovetop): 2 min hands-on, 23 min hands-off", the idea's task list


def build_messages(ctx: StepsContext) -> tuple[Message, ...]:
    user = "\n".join(
        [
            'Write the steps for this recipe as {"steps": [...]}.',
            f"- title: {ctx.title}",
            f"- method: {ctx.method}",
            f"- mood: {ctx.mood}; base_servings: {ctx.base_servings}; about {ctx.active_minutes} hands-on "
            f"minutes, {ctx.total_minutes} minutes in all",
            f"- equipment: {equipment_line(ctx.equipment)}",
            "",
            f"INGREDIENTS (for {ctx.base_servings} servings): " + "; ".join(ctx.ingredients),
            *(["", "TASKS: " + "; ".join(ctx.tasks)] if ctx.tasks else []),
        ]
    )
    return ({"role": "system", "content": STEP_RULES}, {"role": "user", "content": user})
