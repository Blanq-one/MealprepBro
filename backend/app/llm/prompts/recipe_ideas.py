"""Pass 1 of two-stage generation (FLOW_SPEC §13.5): 5–8 ideas in one call, with ingredients and amounts, a
one-line method, equipment and times, and no steps."""

from app.llm.client import Message
from app.llm.prompts.common import IDEA_RULES, IdeaContext, equipment_line, ingredient_lists

PROMPT_VERSION = "recipe_ideas/2"  # /2: the optional freeze note (2b.5 approval)
PURPOSE = "recipe_ideas"


def request_lines(ctx: IdeaContext) -> list[str]:
    minutes = f"at most {ctx.max_active_minutes} hands-on minutes"
    if ctx.max_total_minutes is not None:
        minutes += f", at most {ctx.max_total_minutes} minutes in all"
    lines = [
        f"- mood: {ctx.mood} ({minutes})",
        f'- base_servings: {ctx.base_servings}; meal_slots must include "{ctx.slot}"',
    ]
    if ctx.kcal_per_portion:
        lines.append(
            f"- portion size: about {ctx.kcal_per_portion} kcal per serving, as a rough guide only (the app "
            "does all the math; never write numbers like this in the recipe)"
        )
    lines.append(f"- available equipment: {equipment_line(ctx.equipment)}")
    if ctx.must_use:
        lines.append(f"- use these (each idea uses at least one; as many as fit): {'; '.join(ctx.must_use)}")
    if ctx.may_buy:
        lines.append(f"- may also use these, which can be bought: {'; '.join(ctx.may_buy)}")
    if ctx.use_up:
        lines.append(f"- use these up if they fit: {'; '.join(ctx.use_up)}")
    lines += [f"- {hint}" for hint in ctx.hints]
    lines += [f"- {rule}" for rule in ctx.substitution_rules]
    if ctx.avoid_titles:
        lines.append(f"- different from these existing recipes: {'; '.join(ctx.avoid_titles)}")
    return lines


def build_messages(ctx: IdeaContext) -> tuple[Message, ...]:
    head = (
        f"Write {ctx.count} different {ctx.slot.replace('_', ' ')} idea{'s' if ctx.count != 1 else ''} "
        'as {"ideas": [...]}.'
    )
    user = "\n".join([head, *request_lines(ctx)]) + "\n\n" + ingredient_lists(ctx)
    return ({"role": "system", "content": IDEA_RULES}, {"role": "user", "content": user})
