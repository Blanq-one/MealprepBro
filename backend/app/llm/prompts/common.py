"""Shared prompt pieces: the rules every generation call states, and the context the planner passes in."""

from dataclasses import dataclass

SYSTEM_RULES = """\
You write practical meal-prep recipes for one person's weekly plan. You do only the creative part: recipe \
ideas, ingredient names with raw quantities, and clear cooking steps. The app computes all nutrition, cost, \
safe internal temperatures and storage times itself.

Rules:
1. Use only ingredient names from the INGREDIENTS list, spelled exactly as listed.
2. Never use anything on the NEVER USE list, and never mention those foods in any text.
3. Quantities are raw, dry or as-sold amounts for base_servings: uncooked rice and pasta, raw meat, dry \
lentils, canned goods as sold. Use g for meat, grains and other calorie-dense foods; tsp, tbsp or cup for \
liquids and spices; count for whole items such as eggs.
4. Never write calories, protein/carb/fat amounts or nutrient claims, prices or cost words (cheap, budget, \
deal, sale), internal food temperatures or thermometer checks, how many days food keeps, or health claims. \
Appliance temperatures and cooking, flipping, resting, marinating and chilling times are welcome.
5. To check doneness of meat, poultry, fish or eggs, set doneness_check_for on that step to the ingredient \
name; the app adds the safe temperature.
6. Every recipe needs at least one prep step and a portioning step that says how to divide it into \
containers. Oven and air-fryer steps need appliance_temp_f.
7. List every piece of equipment the steps use, chosen only from the available equipment.
8. active_minutes is hands-on time; total_minutes also includes waiting (simmering, chilling, soaking).
9. Every ingredient a step uses must be in the recipe's ingredient list, including water and salt.
10. Reply with JSON only."""


@dataclass(frozen=True)
class GenerationContext:
    """What the planner asks for. Plain data: the prompt builders never read the database."""

    slot: str
    mood: str
    count: int
    max_active_minutes: int
    kcal_per_portion: int  # a rough size guide only; the app computes the real numbers
    base_servings: int
    equipment: tuple[str, ...]
    vocabulary: tuple[str, ...]
    never_use: tuple[str, ...]
    use_up: tuple[str, ...] = ()
    avoid_titles: tuple[str, ...] = ()
    substitution_rules: tuple[str, ...] = ()


def ingredient_lists(ctx: "GenerationContext | IdeaContext") -> str:
    never = ", ".join(ctx.never_use) if ctx.never_use else "(nothing extra)"
    return f"NEVER USE: {never}\n\nINGREDIENTS: {', '.join(ctx.vocabulary)}"


# ---------------- two-stage generation (Phase 2b, FLOW_SPEC §13.5) ----------------
IDEA_RULES = """\
You suggest practical recipes for one person's meals. You do only the creative part: recipe ideas and \
ingredient names with raw quantities; the steps are written later. The app computes all nutrition, cost, \
safe internal temperatures and storage times itself.

Rules:
1. Use only ingredient names from the INGREDIENTS list, spelled exactly as listed.
2. Never use anything on the NEVER USE list, and never mention those foods.
3. Quantities are raw, dry or as-sold amounts for base_servings: uncooked rice and pasta, raw meat, dry \
lentils, canned goods as sold. Use g for meat, grains, fresh herbs, leafy greens and other solid foods; tsp, \
tbsp or cup for liquids and spices; count for whole items such as eggs.
4. List every ingredient the cooking will use, including water, salt and oil.
5. Never write calories, protein/carb/fat amounts or nutrient claims, prices or cost words (cheap, budget, \
deal, sale), internal food temperatures, how many days food keeps, or health claims.
6. method is one plain line saying how it's cooked.
7. equipment lists every appliance the cooking needs, chosen only from the available equipment; pots, \
pans, sheet pans and knives aren't equipment.
8. active_minutes is hands-on time; total_minutes also includes waiting (simmering, chilling, soaking).
9. Reply with JSON only."""

STEP_RULES = """\
You write clear, practical cooking steps for one saved recipe. Its ingredients, amounts, equipment and \
times are fixed: never add, drop or change an ingredient or an amount. The app computes all nutrition, cost, \
safe internal temperatures and storage times itself.

Rules:
1. Use only the listed ingredients, by the names given, and only the listed equipment.
2. Include at least one prep step, and a portioning step that says how to divide it into containers.
3. Oven and air-fryer steps need appliance_temp_f. Appliance temperatures and cooking, flipping, resting, \
marinating and chilling times are welcome.
4. To check doneness of meat, poultry, fish or eggs, set doneness_check_for on that step to the ingredient \
name; the app adds the safe temperature.
5. Never write calories, nutrient amounts or claims, prices or cost words, internal food temperatures or \
thermometer checks, how many days food keeps, or health claims.
6. Reply with JSON only."""


@dataclass(frozen=True)
class IdeaContext:
    """What one ideas call asks for, as plain text (short names, FLOW_SPEC §13.5). The prompt builders never
    read the database."""

    slot: str
    mood: str
    count: int
    max_active_minutes: int
    base_servings: int
    equipment: tuple[str, ...]
    vocabulary: tuple[str, ...]
    never_use: tuple[str, ...]
    max_total_minutes: int | None = None  # Quick
    kcal_per_portion: int | None = None  # a rough size guide only; the app computes the real numbers
    must_use: tuple[str, ...] = ()  # meal now: your items, open packages and soonest-expiring first
    may_buy: tuple[str, ...] = ()  # meal now: your "could buy" items
    hints: tuple[str, ...] = ()  # goal hints as ingredient directions, never as claims
    use_up: tuple[str, ...] = ()  # meal prep: lots to use up
    avoid_titles: tuple[str, ...] = ()
    substitution_rules: tuple[str, ...] = ()


def equipment_line(equipment: tuple[str, ...]) -> str:
    return ", ".join(equipment) if equipment else "none (no-cook only)"
