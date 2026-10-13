"""API models for recipes and rendered recipe versions (Phase 1)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.api import NutritionOut, StoreCostOut
from app.schemas.cards import CostLineOut, MissingLineOut, SearchContextOut, SwapLineOut


class BudgetLine(BaseModel):
    """recipe_ingredient.budget (JSONB; the 2b.6 approval, item 4): a budget equivalent of the line's
    (classic) ingredient, in base units for the recipe's base servings like the line, and its authored
    amount."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    ingredient_id: int
    quantity: Decimal = Field(gt=0)
    unit: Literal["g", "ml", "count"]
    authored_quantity: Decimal = Field(gt=0)
    authored_unit: str = Field(min_length=1, max_length=40)


class RenderedLineOut(BaseModel):
    ingredient_id: int
    name: str
    display: str  # "1¼ tsp salt"
    preparation: str | None
    optional: bool
    amount_display: str = ""  # "1¼ tsp": the amount alone
    portion_note: str | None = None  # "1 scoop per portion · 4 scoops for the batch of 4" (A1)
    line_id: int | None = None  # the line's ⋯ (step 2b.6): its options are GET …/lines/{line_id}/options


class RenderedStepOut(BaseModel):
    section: str
    text: str
    duration_minutes: int | None
    appliance_temp_f: int | None
    safety_note: str | None
    added_by_app: bool
    stage: int | None = None  # a prep item's stage (step 2b.10); None for a dish
    flag: str | None = None  # your version cooks differently in this step (step 2b.6, AA8)


class StorageOut(BaseModel):
    """How a prep item keeps after a stage (code, domain/prep_storage.py; FLOW_SPEC §19.4)."""

    stored: bool  # prep can stop here
    made_on_the_day: bool  # no storage row: made fresh on the eating day
    fridge_days: int
    freezer: bool
    note: str  # "Keeps 3 days in the fridge (your setting, FoodSafety.gov ...: 3 to 4 days)."
    sources: list[str]  # "FoodSafety.gov Cold Food Storage Chart: Fresh poultry, ... (1 to 2 days; 9 months)"


class PrepStageOut(BaseModel):
    n: int
    state: str  # raw | marinated | partly_cooked | cooked
    state_display: str  # "Marinated"
    storage: StorageOut


class PrepItemOut(BaseModel):
    """A prep item's page (step 2b.10, FLOW_SPEC §19.10): its stages and how it keeps after each."""

    label: str  # "spiced chicken", for meal names
    brings: str  # protein | base | vegetables | sauce | dish
    pairs_with: list[str]
    stages: list[PrepStageOut]


class AssemblyItemOut(BaseModel):
    recipe_id: int
    version_id: int  # its default version: each item opens its own page
    kind: str
    title: str
    label: str
    brings: str
    portions: Decimal  # per person
    portions_display: str  # "1 portion", "½ portion"
    min_portions: Decimal
    max_portions: Decimal
    step: Decimal
    kcal: int  # for these portions
    protein_g: Decimal


class AssemblyOut(BaseModel):
    """An assembly's page (step 2b.10, FLOW_SPEC §19.10): its items, add-ons and eating-day instruction; the
    page's numbers (per_portion, costs) are its items' portions plus its add-ons, by code."""

    name: str
    items: list[AssemblyItemOut]
    instruction: str


class RecipeVersionOut(BaseModel):
    version_id: int
    recipe_id: int
    version_number: int
    title: str
    description: str
    badge: str | None  # "draft" for seed versions
    origin: str
    meal_slots: list[str]
    mood: str
    cuisine: str | None
    flavor_tags: list[str]
    equipment: list[str]
    freezer_friendly: bool  # shown as "Freezes well"
    freeze_note: str | None = None  # how to freeze it: "Freeze the chicken and rice; make the sauce fresh"
    base_servings: int
    portions: int
    portion_size: str
    active_minutes: int
    total_minutes: int
    time_note: str  # LLM time estimates are labeled "est."
    lines: list[RenderedLineOut]
    steps: list[RenderedStepOut]
    per_container: str
    labels: list[str]
    heme_note: str | None
    per_portion: NutritionOut
    costs: list[StoreCostOut]
    incomplete_reasons: list[str]
    change_summary: str | None
    created_at: datetime
    # Phase 2b
    dish_category: (
        str  # drink | dessert | oats | eggs | wrap | sandwich | soup | curry | pasta | salad | bowl |
    )
    # roast | snack | other (the app shows its icon)
    is_favorite: bool
    is_saved: bool
    steps_ready: bool = True  # False for an idea whose steps are written on first open (step 2b.3b)
    # with ?search=<id>: that search's coverage and substitute lines for this recipe (step 2b.3a)
    search_context: SearchContextOut | None = None
    # step 2b.10: dish | prep_item | assembly; a prep item's stages, an assembly's items (its lines are its
    # add-ons, per portion)
    kind: str = "dish"
    prep: PrepItemOut | None = None
    assembly: AssemblyOut | None = None
    # step 2b.7: Not for me (F24) is on: left out of every suggestion and plan until shown again
    is_hidden: bool = False
    # step 2b.6 (AA5, AA8): your own version ("Your version: chicken breast instead of chicken thigh" is its
    # change_summary), the version it came from, and whether a step is flagged (Rewrite steps for this change)
    your_version: bool = False
    parent_version_id: int | None = None
    can_rewrite_steps: bool = False


class HiddenRecipeOut(BaseModel):
    """Settings, Hidden recipes (step 2b.7, F24): a recipe you hid with Not for me, at its default version."""

    recipe_id: int
    version_id: int
    title: str
    kind: str  # dish | prep_item | assembly
    dish_category: str
    hidden_at: datetime


class RecipeVersionSummaryOut(BaseModel):
    version_id: int
    version_number: int
    created_by: str
    is_draft: bool
    change_summary: str | None
    created_at: datetime


class RecipeOut(BaseModel):
    recipe_id: int
    title: str
    origin: str
    family: str | None
    default_version_id: int | None
    versions: list[RecipeVersionSummaryOut]
    default_version: RecipeVersionOut | None


class SavedRecipeOut(BaseModel):
    """A Saved-list card (C7). Every number is a display string from code, per portion, at your household's
    portions (as the recipe page shows them); coverage is against your current pantry (step 2b.3a)."""

    recipe_id: int
    version_id: int
    title: str
    dish_category: str
    badges: list[Literal["favorite", "saved", "new", "draft"]]
    steps_ready: bool
    portions: int  # your household size
    portion_size: str  # your portion size (the recipe page's portion_size for the same numbers)
    portions_display: str  # "1 portion" / "for 2 people"
    numbers: list[str]  # "540 kcal", "41 g protein", "35 min", "$2.10 a portion est.", "$4.29 to buy today"
    uses: list[str]  # your items it uses
    could_buy: list[CostLineOut]  # always empty here (no could-buy items outside a search)
    missing: list[MissingLineOut]  # what you'd buy, with its price (M11)
    swaps: list[SwapLineOut] = Field(default_factory=list)  # what you can make with something you have
    saved_at: datetime


# ---------------- step 2b.6: a line's ⋯ (AA5, AA8) ----------------
class SwapChoiceOut(BaseModel):
    """One substitute for a line, with the change per portion (code-computed)."""

    ingredient_id: int
    name: str
    display: str  # its amount for the recipe as written: "150 g"
    numbers: list[str]  # per portion: "+12 kcal", "−4.5 g protein", "+$0.30"
    note: str | None = None  # an accepted pair's note
    cooking_note: str | None = None  # it cooks differently: the steps that name it are flagged


class LeaveOutOut(BaseModel):
    allowed: bool  # only garnishes, optional lines, seasonings and small aromatics
    reason: str | None = None  # why not
    numbers: list[str] = Field(default_factory=list)  # per portion
    warning: str | None = None  # "Protein drops by 12.5 g a portion."


class ShoppingTargetOut(BaseModel):
    """Where I'm out of this adds the item: the plan you opened it from, or your current plan."""

    plan_id: int | None
    list_id: int | None
    can_add: bool
    reason: str | None = None  # why not: no plan, or the trip is done


class BudgetPairOut(BaseModel):
    """A line's classic ingredient and its budget equivalent (the 2b.6 approval, item 4)."""

    classic: str  # "tomato"
    budget: str  # "canned diced tomatoes"
    budget_display: str  # "360 ml canned diced tomatoes"


class LineOptionsOut(BaseModel):
    line_id: int
    ingredient_id: int
    name: str
    display: str  # the line as written: "600 g chicken thigh, boneless skinless"
    swaps: list[SwapChoiceOut]
    leave_out: LeaveOutOut
    in_pantry: bool  # you have some
    never_used: bool  # already on Foods I don't eat (or always excluded)
    shopping: ShoppingTargetOut
    # a budget equivalent: a budget tier picks a side by price; use_classic / use_budget fixes the line
    pair: BudgetPairOut | None = None


class RecipeEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: int
    # use_classic / use_budget (the 2b.6 approval, item 4): fix a line with a budget equivalent to one side
    action: Literal["swap", "leave_out", "use_classic", "use_budget"]
    ingredient_id: int | None = None  # swap: one of the line's swaps
    batch_id: int | None = None  # opened from a plan meal: may that batch switch to your version?


class RecipeEditOut(BaseModel):
    """Your new version (it's the recipe's default from now on), and whether this week's plan can take it."""

    version: RecipeVersionOut
    note: str  # "Your version: chicken breast instead of chicken thigh"
    cooking_note: str | None = None  # it cooks differently: Rewrite steps for this change is offered
    flagged_steps: list[int] = Field(default_factory=list)
    batch_id: int | None = None
    can_update_plan: bool = False  # Also update this week's plan
    plan_note: str | None = None  # why not: "Mon 12's batch is already cooked, so it keeps …"
