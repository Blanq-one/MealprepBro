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
export type SettingsOut = S["SettingsOut"];
export type UserSettings = S["UserSettings"];
export type DietReview = S["DietReviewOut"];
export type Problem = S["ProblemOut"];
export type MealSlot = S["MealSlot"];
export type StorageLocation = S["StorageLocation"];
export type PortionSize = S["PortionSize"];
export type NutritionPriority = S["NutritionPriority"];
