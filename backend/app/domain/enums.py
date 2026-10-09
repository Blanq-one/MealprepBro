"""Shared enums (BUILD_PLAN §6.1). Stored as text in the DB; validated here."""

from enum import StrEnum


class MealSlot(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    PROTEIN_DESSERT = "protein_dessert"
    DRINK = "drink"


class NutritionPriority(StrEnum):
    PROTEIN = "protein"
    CARB = "carb"
    IRON = "iron"
    BALANCED = "balanced"
    # Future modes (PRD §3): accepted by the enum, rejected by the planner until implemented.
    FIBER = "fiber"
    LOWER_FAT = "lower_fat"
    SATIETY = "satiety"
    VEGETABLE = "vegetable"


class CalorieMode(StrEnum):
    STRICT_DAILY = "strict_daily"  # hard daily ceiling
    WEEKLY = "weekly"  # hard weekly ceiling + per-day band


class RecipeMood(StrEnum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    FANCY = "fancy"


class PortionSize(StrEnum):
    SMALL = "small"  # 0.75
    NORMAL = "normal"  # 1.00
    LARGE = "large"  # 1.25
    EXTRA_LARGE = "extra_large"  # 1.50


class PlanningMode(StrEnum):
    """Per-request: cook from what you have (purchases off unless you allow a top-up), or plan a shop."""

    INVENTORY = "inventory"
    SHOP = "shop"


class GroceryMode(StrEnum):
    BALANCED = "balanced"
    CHEAPEST = "cheapest"
    HEALTHIER = "healthier"
    SEASONAL = "seasonal"


class Equipment(StrEnum):
    STOVETOP = "stovetop"
    OVEN = "oven"
    AIR_FRYER = "air_fryer"
    MICROWAVE = "microwave"
    RICE_COOKER = "rice_cooker"
    PRESSURE_COOKER = "pressure_cooker"
    SLOW_COOKER = "slow_cooker"
    BLENDER = "blender"
    FOOD_PROCESSOR = "food_processor"
    GRILL = "grill"


class IngredientCategory(StrEnum):
    PROTEIN = "protein"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"
    GRAIN = "grain"
    LEGUME = "legume"
    DAIRY = "dairy"
    FAT_OIL = "fat_oil"
    NUT_SEED = "nut_seed"
    SPICE = "spice"
    CONDIMENT = "condiment"
    SWEETENER = "sweetener"
    SUPPLEMENT = "supplement"
    BEVERAGE = "beverage"
    OTHER = "other"


class IngredientRole(StrEnum):
    PROTEIN = "protein"
    CARB = "carb"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"
    DAIRY = "dairy"
    FAT = "fat"
    SAUCE = "sauce"
    SEASONING = "seasoning"
    GARNISH = "garnish"
    OTHER = "other"


class InstructionSection(StrEnum):
    PREP = "prep"
    MARINATE = "marinate"
    STOVETOP = "stovetop"
    OVEN = "oven"
    AIR_FRYER = "air_fryer"
    RICE = "rice"
    MICROWAVE = "microwave"
    NO_COOK = "no_cook"
    ASSEMBLY = "assembly"
    PORTIONING = "portioning"
    STORAGE = "storage"
    REHEATING = "reheating"


class StorageLocation(StrEnum):
    PANTRY = "pantry"
    FRIDGE = "fridge"
    FREEZER = "freezer"


class NutritionSource(StrEnum):
    USDA = "usda"
    PACKAGE_LABEL = "package_label"  # shown as "package label"
    MANUAL = "manual"
    DERIVED = "derived"


class RecipeOrigin(StrEnum):
    SEED = "seed"
    LLM = "llm"
    USER = "user"


class PriceSource(StrEnum):
    MANUAL = "manual"
    IN_STORE = "in_store"
    RECEIPT = "receipt"
    ESTIMATE = "estimate"
    API = "api"


class PriceBasis(StrEnum):
    PER_PACKAGE = "per_package"
    PER_WEIGHT = "per_weight"
    PER_COUNT = "per_count"
