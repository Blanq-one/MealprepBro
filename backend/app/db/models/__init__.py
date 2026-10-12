"""All ORM models. Importing this package registers every table on Base.metadata."""

from app.db.models.cook import CookSearch, FeedbackEvent, RecipeFavorite, RecipeSaved
from app.db.models.exposure import LoginAttempt, PlanCandidate
from app.db.models.ingredient import (
    Ingredient,
    IngredientAlias,
    IngredientNutrient,
    IngredientSubstitution,
    IngredientUnit,
)
from app.db.models.inventory import InventoryEvent, InventoryItem
from app.db.models.llm import GenerationRun, LlmCall
from app.db.models.nutrition import Nutrient, UsdaFood, UsdaFoodNutrient, UsdaFoodPortion, UsdaNutrient
from app.db.models.plan import (
    GroceryList,
    GroceryListItem,
    MealPlan,
    PlanBatchIngredient,
    PlanCookBatch,
    PlanFinishTask,
    PlanMeal,
    PlanMealComponent,
)
from app.db.models.recipe import (
    AssemblyComponent,
    Recipe,
    RecipeFamily,
    RecipeIngredient,
    RecipeStep,
    RecipeVersion,
)
from app.db.models.store import PriceObservation, Product, Store
from app.db.models.user import AppUser, IngredientPreference, UserSettingsRow

__all__ = [
    "AppUser",
    "AssemblyComponent",
    "CookSearch",
    "FeedbackEvent",
    "GenerationRun",
    "GroceryList",
    "GroceryListItem",
    "Ingredient",
    "IngredientAlias",
    "IngredientNutrient",
    "IngredientPreference",
    "IngredientSubstitution",
    "IngredientUnit",
    "InventoryEvent",
    "InventoryItem",
    "LlmCall",
    "LoginAttempt",
    "MealPlan",
    "Nutrient",
    "PlanBatchIngredient",
    "PlanCandidate",
    "PlanCookBatch",
    "PlanFinishTask",
    "PlanMeal",
    "PlanMealComponent",
    "PriceObservation",
    "Product",
    "Recipe",
    "RecipeFamily",
    "RecipeFavorite",
    "RecipeIngredient",
    "RecipeSaved",
    "RecipeStep",
    "RecipeVersion",
    "Store",
    "UsdaFood",
    "UsdaFoodNutrient",
    "UsdaFoodPortion",
    "UsdaNutrient",
    "UserSettingsRow",
]
