"""Targeted revision of one generated recipe that failed the app's checks."""

from collections.abc import Sequence

from app.llm.client import Message
from app.llm.prompts.common import SYSTEM_RULES, GenerationContext, ingredient_lists

PROMPT_VERSION = "recipe_revision/1"
PURPOSE = "recipe_revision"


def build_messages(ctx: GenerationContext, recipe_json: str, problems: Sequence[str]) -> tuple[Message, ...]:
    bullets = "\n".join(f"- {p}" for p in problems)
    user = (
        "Revise this recipe so it passes every check. Keep the idea, flavors and servings; change only what "
        "the problems require. Reply with the single revised recipe object.\n\n"
        f"Problems:\n{bullets}\n\n"
        f"Available equipment: {', '.join(ctx.equipment) if ctx.equipment else 'none (no-cook only)'}\n\n"
        f"Recipe:\n{recipe_json}\n\n" + ingredient_lists(ctx)
    )
    return ({"role": "system", "content": SYSTEM_RULES}, {"role": "user", "content": user})
