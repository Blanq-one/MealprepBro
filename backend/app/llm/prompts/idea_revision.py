"""Revision of ideas that failed the app's checks (FLOW_SPEC §13.5). Runs only when no idea in a batch passes,
and sends at most 3 failed ideas with their problems, so the call stays short."""

from collections.abc import Sequence

from app.llm.client import Message
from app.llm.prompts.common import IDEA_RULES, IdeaContext, equipment_line, ingredient_lists
from app.llm.prompts.recipe_ideas import request_lines

PROMPT_VERSION = "idea_revision/2"  # /2: the optional freeze note (2b.5 approval)
PURPOSE = "idea_revision"


def build_messages(ctx: IdeaContext, failed: Sequence[tuple[str, Sequence[str]]]) -> tuple[Message, ...]:
    """`failed`: (the idea as JSON, its problems) for each idea sent back."""
    parts = [
        "None of these ideas passed the app's checks. Fix each one so it passes every check: keep the idea, "
        'flavors and servings, and change only what the problems require. Reply as {"ideas": [...]}.',
    ]
    for n, (idea_json, problems) in enumerate(failed, start=1):
        bullets = "\n".join(f"- {p}" for p in problems)
        parts.append(f"Idea {n}:\n{idea_json}\nProblems:\n{bullets}")
    context = [line for line in request_lines(ctx) if not line.startswith("- different from")]
    parts.append("Requirements:\n" + "\n".join(context))
    parts.append(f"Available equipment: {equipment_line(ctx.equipment)}")
    user = "\n\n".join(parts) + "\n\n" + ingredient_lists(ctx)
    return ({"role": "system", "content": IDEA_RULES}, {"role": "user", "content": user})
