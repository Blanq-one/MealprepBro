// Friendly names for the API models (generated from the backend's OpenAPI by `npm run gen:api`).
import type { components } from "./schema";

type S = components["schemas"];

export type PlanSummary = S["PlanSummaryOut"];
export type PlanListItem = S["PlanListItemOut"];
export type PlanRequest = S["PlanRequest"];
/** What the app sends: everything but week_start has a server default. */
export type PlanRequestBody = Pick<PlanRequest, "week_start"> & Partial<PlanRequest>;
export type PlanStreamEvent = S["PlanStreamEvent"];
export type Day = S["DayOut"];
export type Meal = S["MealOut"];
export type Batch = S["BatchOut"];
export type GenerationRun = S["GenerationRunOut"];
export type GroceryList = S["GroceryListOut"];
export type GroceryGroup = S["GroceryGroupOut"];
export type GroceryItem = S["GroceryItemOut"];
export type GroceryItemPatch = S["GroceryItemPatch"];
export type GroceryComplete = S["GroceryCompleteOut"];
export type BatchDetail = S["BatchDetailOut"];
export type Cooked = S["CookedOut"];
export type RecipeVersion = S["RecipeVersionOut"];
export type Step = S["RenderedStepOut"];
export type InventoryLot = S["InventoryLotOut"];
export type InventoryLotIn = S["InventoryLotIn"];
export type ParsedLot = S["ParsedLotOut"];
export type ParseResult = S["ParseOut"];
export type QuickPick = S["QuickPickOut"];
export type IngredientHit = S["IngredientSearchHitOut"];
export type AmountOption = S["AmountOptionOut"];
export type CustomUnit = S["CustomUnitOut"];
export type BulkItemIn = S["BulkItemIn"];
export type SettingsOut = S["SettingsOut"];
export type UserSettings = S["UserSettings"];
export type DietReview = S["DietReviewOut"];
export type Preference = S["PreferenceOut"];
export type FrequencyCap = S["FrequencyCapSetting"];
export type CookDay = S["CookDaySetting"];
export type SlotAllocation = S["SlotAllocationSetting"];
export type Equipment = S["Equipment"];
export type RecipeMood = S["RecipeMood"];
export type CalorieMode = S["CalorieMode"];
export type SettingsPreview = S["SettingsPreviewOut"];
export type FieldError = S["FieldErrorOut"];
export type SummaryLine = S["SummaryLineOut"];
export type Store = S["StoreOut"];
export type AlwaysHaveOption = S["AlwaysHaveOptionOut"];
export type SavedRecipe = S["SavedRecipeOut"];
export type Problem = S["ProblemOut"];
export type MealSlot = S["MealSlot"];
export type StorageLocation = S["StorageLocation"];
export type PortionSize = S["PortionSize"];
export type NutritionPriority = S["NutritionPriority"];
// Phase 2b, step 2b.4: the meal-now flow
export type CookAnswers = S["CookAnswers-Input"];
export type ExtraItem = S["ExtraItem-Input"];
export type GoalTile = NonNullable<CookAnswers["goals"]>[number];
export type Suggestion = S["RecipeSuggestionOut"];
export type CookStreamEvent = S["CookStreamEvent"];
export type CookSearch = S["CookSearchOut"];
export type CookMealIn = S["CookMealIn"];
export type CookMealOut = S["CookMealOut"];
export type CookHome = S["CookHomeOut"];
export type LastSearch = S["LastSearchOut"];
export type TodayOut = S["TodayOut"];
export type SavedPreview = S["SavedPreviewOut"];
export type CostLine = S["CostLineOut"];
export type MissingLine = S["MissingLineOut"];
export type SearchContext = S["SearchContextOut"];
export type LineContext = S["LineContextOut"];
export type AddOptions = S["AddOptionsOut"];
export type FormOption = S["FormOut"];
export type Preset = S["PresetOut"];
export type VersionChoice = S["VersionChoiceOut"];
export type Versions = S["VersionsOut"];
export type PantryNote = S["PantryNoteOut"];
// Step 2b.4 approval (M2, M11)
export type CorrectOptions = S["CorrectOptionsOut"];
export type SwapLine = S["SwapLineOut"];
// Step 2b.3b: steps on first open (E19)
export type StepsStreamEvent = S["StepsStreamEvent"];
// Step 2b.7: the plan view's smart prep side and Not for me (F24)
export type MealComponent = S["MealComponentOut"];
export type FinishTask = S["FinishTaskOut"];
export type HiddenRecipe = S["HiddenRecipeOut"];
// Step 2b.6: swap one meal (E5, AA4)
export type SwapOption = S["SwapOptionOut"];
export type SwapMeal = S["SwapMealOut"];
export type SwapStreamEvent = S["SwapStreamEvent"];
export type SwapOptionsBody = Partial<S["SwapOptionsIn"]>;
export type SwapBody = S["SwapIn"];
export type SwapResult = S["SwapOut"];
