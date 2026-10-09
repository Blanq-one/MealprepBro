"""Batch generation of candidate recipes for one uncovered (slot, mood)."""

from app.llm.client import Message
from app.llm.prompts.common import SYSTEM_RULES, GenerationContext, ingredient_lists

PROMPT_VERSION = "candidate_generation/1"
PURPOSE = "candidate_generation"


def build_messages(ctx: GenerationContext) -> tuple[Message, ...]:
    lines = [
        f"Write {ctx.count} different {ctx.slot.replace('_', ' ')} recipe{'s' if ctx.count != 1 else ''} "
        'as {"recipes": [...]}.',
        f"- mood: {ctx.mood} (at most {ctx.max_active_minutes} hands-on minutes)",
        f'- base_servings: {ctx.base_servings}; meal_slots must include "{ctx.slot}"',
        f"- portion size: about {ctx.kcal_per_portion} kcal per serving, as a rough guide only "
        "(the app does all the math; never write numbers like this in the recipe)",
        f"- available equipment: {', '.join(ctx.equipment) if ctx.equipment else 'none (no-cook only)'}",
    ]
    lines += [f"- {rule}" for rule in ctx.substitution_rules]
    if ctx.use_up:
        lines.append(f"- use these up if they fit: {'; '.join(ctx.use_up)}")
    if ctx.avoid_titles:
        lines.append(f"- different from these existing recipes: {'; '.join(ctx.avoid_titles)}")
    user = "\n".join(lines) + "\n\n" + ingredient_lists(ctx)
    return ({"role": "system", "content": SYSTEM_RULES}, {"role": "user", "content": user})
