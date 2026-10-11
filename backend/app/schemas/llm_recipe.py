"""What the LLM returns (BUILD_PLAN §6.3): creative content only.

These models deliberately have NO calorie, macro, cost, safe-temperature or storage-duration fields: code
computes or injects all of those. `extra="forbid"` means a response that adds such a field (e.g.
"calories") fails validation and is retried with the error."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import Equipment, IngredientRole, InstructionSection, MealSlot, RecipeMood


class LLMUnit(StrEnum):
    G = "g"
    KG = "kg"
    OZ = "oz"
    LB = "lb"
    ML = "ml"
    L = "l"
    TSP = "tsp"
    TBSP = "tbsp"
    CUP = "cup"
    FL_OZ = "fl_oz"
    COUNT = "count"
    CLOVE = "clove"
    SLICE = "slice"
    CAN = "can"
    HEAD = "head"
    SCOOP = "scoop"
    # Named units must exist in ingredient_unit for that ingredient, else a domain error.


_SECTION_EQUIPMENT = {
    InstructionSection.OVEN: Equipment.OVEN,
    InstructionSection.AIR_FRYER: Equipment.AIR_FRYER,
    InstructionSection.STOVETOP: Equipment.STOVETOP,
    InstructionSection.MICROWAVE: Equipment.MICROWAVE,
}


class LLMIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80, description="Name from the provided ingredient list")
    quantity: float = Field(gt=0, le=5000, description="Raw/dry, as-purchased amount for base_servings")
    unit: LLMUnit
    preparation: str | None = Field(default=None, max_length=80)
    role: IngredientRole
    component: str | None = Field(default=None, max_length=40)
    optional: bool = False


class LLMStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: InstructionSection
    text: str = Field(min_length=5, max_length=500)  # cooking temps/times welcome; see §7.3
    duration_minutes: int | None = Field(default=None, ge=0, le=720)
    appliance_temp_f: int | None = Field(
        default=None,
        ge=150,
        le=550,
        description="Oven / air-fryer / pan setting. Never an internal food temperature.",
    )
    doneness_check_for: str | None = Field(
        default=None,
        max_length=80,
        description="Ingredient whose doneness is checked here; the app inserts the safe temperature.",
    )


class GeneratedRecipe(BaseModel):
    """Creative content only. Deliberately has NO calorie, macro, cost, safe-temperature or
    storage-duration fields: code computes or injects all of those."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=80)
    description: str = Field(max_length=300)
    meal_slots: list[MealSlot] = Field(min_length=1, max_length=3)
    mood: RecipeMood
    cuisine: str | None = Field(default=None, max_length=40)
    flavor_tags: list[str] = Field(default_factory=list, max_length=6)
    base_servings: int = Field(ge=1, le=12)
    active_minutes: int = Field(ge=1, le=240, description="Hands-on minutes")
    total_minutes: int = Field(ge=1, le=720, description="Start-to-finish minutes, including waiting")
    equipment: list[Equipment] = Field(default_factory=list)  # empty allowed for no-cook recipes
    freezer_friendly: bool
    ingredients: list[LLMIngredient] = Field(min_length=2, max_length=25)
    steps: list[LLMStep] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def _structure(self) -> Self:
        if self.total_minutes < self.active_minutes:
            raise ValueError("total_minutes must be >= active_minutes")
        names = [i.name.strip().lower() for i in self.ingredients]
        if len(set(names)) != len(names):
            raise ValueError("duplicate ingredient names; combine them into one line")
        sections = {s.section for s in self.steps}
        if InstructionSection.PREP not in sections:
            raise ValueError("include at least one PREP step")
        if InstructionSection.PORTIONING not in sections:
            raise ValueError("include a PORTIONING step")
        missing = {
            eq for sec, eq in _SECTION_EQUIPMENT.items() if sec in sections and eq not in self.equipment
        }
        if missing:
            raise ValueError(f"steps use equipment not listed in 'equipment': {sorted(missing)}")
        for sec in (InstructionSection.OVEN, InstructionSection.AIR_FRYER):
            sec_steps = [s for s in self.steps if s.section == sec]
            if sec_steps and all(s.appliance_temp_f is None for s in sec_steps):
                raise ValueError(f"{sec} steps must state an appliance temperature")
        return self


class GeneratedRecipeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipes: list[GeneratedRecipe] = Field(min_length=1, max_length=6)


# ---------------- two-stage generation (Phase 2b, FLOW_SPEC §13.5) ----------------
class IdeaIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80, description="A name from INGREDIENTS, exactly as listed")
    quantity: float = Field(gt=0, le=5000, description="Raw/dry, as-purchased amount for base_servings")
    unit: LLMUnit
    role: IngredientRole


class RecipeIdea(BaseModel):
    """An idea: everything the app needs to check, price and rank a recipe, and no steps (written on first
    open). Creative content only, like GeneratedRecipe: no calorie, macro, cost, temperature or storage
    fields."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=80)
    method: str = Field(min_length=10, max_length=140, description="One line: how it's cooked")
    meal_slots: list[MealSlot] = Field(min_length=1, max_length=3)
    mood: RecipeMood
    base_servings: int = Field(ge=1, le=12)
    active_minutes: int = Field(ge=1, le=240, description="Hands-on minutes")
    total_minutes: int = Field(ge=1, le=720, description="Start-to-finish minutes, including waiting")
    equipment: list[Equipment] = Field(default_factory=list)
    freezer_friendly: bool
    # the seeds' freeze-note rules (SeedRecipe): same bounds, and only on a recipe that freezes well
    freeze_note: str | None = Field(
        default=None,
        min_length=5,
        max_length=200,
        description="Only if freezer_friendly: what to freeze and what to make fresh when serving; else null",
    )
    ingredients: list[IdeaIngredient] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def _structure(self) -> Self:
        if self.total_minutes < self.active_minutes:
            raise ValueError("total_minutes must be >= active_minutes")
        if self.freeze_note is not None and not self.freezer_friendly:
            raise ValueError("freeze_note needs freezer_friendly: true; otherwise set it to null")
        names = [i.name.strip().lower() for i in self.ingredients]
        if len(set(names)) != len(names):
            raise ValueError("duplicate ingredient names; combine them into one line")
        return self


class RecipeIdeaBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ideas: list[RecipeIdea] = Field(min_length=1, max_length=8)


class RecipeSteps(BaseModel):
    """The steps for one saved idea (LLMStep unchanged). Validated together with the idea as one
    GeneratedRecipe, so every step check above runs as it is."""

    model_config = ConfigDict(extra="forbid")
    steps: list[LLMStep] = Field(min_length=3, max_length=30)


def idea_as_recipe(idea: RecipeIdea, steps: list[LLMStep]) -> GeneratedRecipe:
    """An idea and its steps as one GeneratedRecipe (raises ValidationError when the steps break a rule)."""
    return GeneratedRecipe(
        title=idea.title,
        description=idea.method,
        meal_slots=idea.meal_slots,
        mood=idea.mood,
        base_servings=idea.base_servings,
        active_minutes=idea.active_minutes,
        total_minutes=idea.total_minutes,
        equipment=idea.equipment,
        freezer_friendly=idea.freezer_friendly,
        ingredients=[
            LLMIngredient(name=i.name, quantity=i.quantity, unit=i.unit, role=i.role)
            for i in idea.ingredients
        ],
        steps=steps,
    )
