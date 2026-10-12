// API-shaped test data (types from the generated schema, so a backend change breaks these at compile time).
import type {
  AddOptions,
  BatchDetail,
  CookHome,
  GroceryItem,
  InventoryLot,
  GroceryList,
  PlanSummary,
  QuickPick,
  RecipeVersion,
  SettingsOut,
  SettingsPreview,
  Store,
  Suggestion,
  UserSettings,
} from "@/lib/api/types";

/** The seeded default settings (backend/app/seed/data/settings_default.json). */
export function userSettings(overrides: Partial<UserSettings> = {}): UserSettings {
  return {
    schema_version: 3,
    household_size: 1,
    always_have: [],
    default_budget_cents: null,
    onboarding_completed: false,
    daily_kcal_target: 1800,
    calorie_mode: "weekly",
    daily_band_kcal: 150,
    weekly_under_pct: 3,
    daily_under_pct: 5,
    slot_allocations: [
      { slot: "breakfast", kcal: 400 },
      { slot: "lunch", kcal: 550 },
      { slot: "dinner", kcal: 650 },
      { slot: "protein_dessert", kcal: 200 },
    ],
    daily_protein_target_g: 100,
    nutrition_priority: "protein",
    secondary_priority: null,
    grocery_mode: "balanced",
    equipment: ["stovetop", "oven", "air_fryer", "microwave"],
    cook_schedule: [
      { weekday: "mon", is_cook_day: true, cook_minutes: 90, mood: "medium", weeknight_minutes: 30 },
      { weekday: "tue", is_cook_day: false, cook_minutes: 0, mood: "simple", weeknight_minutes: 30 },
      { weekday: "wed", is_cook_day: true, cook_minutes: 90, mood: "medium", weeknight_minutes: 30 },
      { weekday: "thu", is_cook_day: true, cook_minutes: 90, mood: "medium", weeknight_minutes: 30 },
      { weekday: "fri", is_cook_day: false, cook_minutes: 0, mood: "simple", weeknight_minutes: 30 },
      { weekday: "sat", is_cook_day: true, cook_minutes: 90, mood: "medium", weeknight_minutes: 30 },
      { weekday: "sun", is_cook_day: true, cook_minutes: 90, mood: "medium", weeknight_minutes: 30 },
    ],
    leftover_fridge_days: 3,
    excluded_diet_tags: ["beef"],
    frequency_caps: [{ label: "Pork as a meal component", target_type: "tag", target: "pork", max_meals_per_week: 1, never_favor: true }],
    store_order: ["Stop & Shop", "Price Rite"],
    store_split_min_savings_cents: 500,
    default_portion_size: "normal",
    region_code: "MA",
    units: "us",
    usual_versions: {},
    daily_amount_caps: [{ label: "Protein powder", ingredient: "protein-powder-double-chocolate", unit: "scoop", usual: 1, maximum: 2 }],
    cook_time_note: false,
    ...overrides,
  };
}

export function settingsOut(overrides: Partial<UserSettings> = {}): SettingsOut {
  return {
    settings: userSettings(overrides),
    preferences: [],
    diet_review: [
      { ingredient_id: 40, slug: "gelatin-unflavored", name: "gelatin, unflavored", note: "Source not stated; may be bovine.", decision: "held" },
      { ingredient_id: 41, slug: "marshmallows", name: "marshmallows", note: null, decision: "held" },
    ],
  };
}

export function preview(overrides: Partial<SettingsPreview> = {}): SettingsPreview {
  return {
    valid: true,
    errors: [],
    kcal_planned_display: "1,800 of 1,800 kcal a day planned",
    summary: [
      { key: "people", label: "People", value: "1 person" },
      { key: "budget", label: "Weekly budget", value: "No limit" },
      { key: "targets", label: "Daily targets", value: "1,800 kcal · 100 g protein" },
      { key: "meals", label: "Meals", value: "Breakfast 400 · Lunch 550 · Dinner 650 · Protein dessert 200 (1,800 of 1,800 kcal planned)" },
      { key: "cook_days", label: "Cook days", value: "Mon, Wed, Thu, Sat, Sun · 1 h 30 min start to finish" },
      { key: "equipment", label: "Kitchen", value: "Stovetop, Oven, Air fryer, Microwave" },
      { key: "stores", label: "Stores", value: "1 Stop & Shop · 2 Price Rite" },
      { key: "food_rules", label: "Food rules", value: "Beef: never · Pork: up to 1 meal a week · 2 held, 0 allowed" },
      { key: "always_have", label: "Always have", value: "Nothing yet" },
      { key: "daily_caps", label: "Daily caps", value: "Protein powder: usually 1 scoop a day, at most 2 scoops" },
    ],
    settings: null,
    ...overrides,
  };
}

export const stores: Store[] = [
  { id: 1, name: "Stop & Shop", priority: 1, order: 1 },
  { id: 2, name: "Price Rite", priority: 2, order: 2 },
];

export function quickPick(overrides: Partial<QuickPick> = {}): QuickPick {
  return {
    ingredient_id: 1,
    name: "chicken thigh, boneless skinless",
    category: "protein",
    product_id: 12,
    quantity: "907.185",
    unit: "g",
    display: "family pack, 2 lb (907 g)",
    location: "fridge",
    amount_options: [
      { key: "full", quantity: "907.185", unit: "g", display: "Full · 2 lb (907 g)" },
      { key: "three_quarters", quantity: "680.389", unit: "g", display: "¾ · 1.5 lb (680 g)" },
      { key: "half", quantity: "453.593", unit: "g", display: "½ · 1 lb (454 g)" },
      { key: "quarter", quantity: "226.796", unit: "g", display: "¼ · 8 oz (227 g)" },
    ],
    custom_units: [
      { unit: "lb", label: "lb", step: "0.25", start: "2" },
      { unit: "oz", label: "oz", step: "1", start: "32" },
      { unit: "g", label: "g", step: "25", start: "900" },
    ],
    ...overrides,
  };
}

export function plan(overrides: Partial<PlanSummary> = {}): PlanSummary {
  return {
    id: 7,
    week_start: "2026-10-12",
    status: "draft",
    kind: null,
    calorie_mode: "weekly",
    kcal_target_week: 12600,
    kcal_planned_week: 12430,
    nutrition_focus: "protein",
    secondary_focus: "iron",
    planning_mode: "shop",
    purchase_limit_cents: 4200,
    protein_target_g_per_day: 100,
    estimated_cost_cents: 3870,
    estimated_cost_display: "$38.70",
    cost_complete: true,
    cost_note: null,
    store_totals: [{ store_id: 1, store_name: "Stop & Shop", cents: 3870, display: "$38.70" }],
    cooking_minutes_total: 210,
    meals_count: 28,
    protein_g_week: "812.0",
    protein_g_per_day: "116.0",
    costs: {
      cash_cents: 3870,
      cash_display: "$38.70",
      regular_cash_cents: 3870,
      stock_up_cash_cents: 0,
      eaten_cents: 3410,
      eaten_display: "$34.10",
      from_inventory_cents: 0,
      leftover_cents: 460,
      leftover_display: "$4.60",
      frozen_portions_cents: 0,
      expected_waste_cents: 120,
      expected_waste_display: "$1.20",
      complete: true,
      unpriced: [],
      cash_split_display: "$38.70 groceries",
    },
    leftovers: [],
    freeze: [],
    days: [
      {
        day: "2026-10-12",
        is_cook_day: true,
        kcal: 1790,
        kcal_target: 1800,
        protein_g: "118.0",
        hands_on_minutes: 45,
        elapsed_minutes: 70,
        chill_minutes: 0,
        cook_minutes_available: 45,
        meals: [
          {
            eat_on: "2026-10-12",
            slot: "lunch",
            recipe_version_id: 3,
            recipe_id: 3,
            title: "Chicken over rice",
            is_draft: true,
            kcal: 560,
            protein_g: "42.0",
            from_freezer: false,
            cook_batch_id: 11,
            note: null,
            dish_category: "bowl",
            cost_cents: 210,
            cost_display: "$2.10",
            storage: "fresh",
            source_display: "Cooked today",
          },
        ],
        cook_note: "Cook: Chicken over rice (4 portions)",
        cost_cents: 840,
        cost_display: "$8.40",
        freeze_steps: [],
        freeze_today: [],
        thaw_notes: [],
        timeline: [],
        time_display: null,
      },
      {
        day: "2026-10-13",
        is_cook_day: false,
        kcal: 1780,
        kcal_target: 1800,
        protein_g: "110.0",
        hands_on_minutes: 0,
        elapsed_minutes: 0,
        chill_minutes: 0,
        cook_minutes_available: 0,
        meals: [],
        cook_note: "Nothing to cook, eating prepped meals",
        cost_cents: 820,
        cost_display: "$8.20",
        freeze_steps: [],
        freeze_today: [],
        thaw_notes: [],
        timeline: [],
        time_display: null,
      },
    ],
    batches: [],
    warnings: [],
    notes: [],
    generation_run_id: 4,
    prep_notes: null,
    header: null,
    household_size: 1,
    proven_best: true,
    ...overrides,
  };
}

export function groceryItem(overrides: Partial<GroceryItem> = {}): GroceryItem {
  return {
    id: 1,
    ingredient_id: 1,
    name: "chicken thigh, boneless skinless",
    category: "protein",
    store_id: 1,
    store_name: "Stop & Shop",
    product_name: "Family pack",
    needed: "1,580 g (3.48 lb)",
    from_inventory: null,
    to_buy: "1 × Family pack",
    packages: 1,
    estimated_cost_cents: 1347,
    estimated_cost_display: "$13.47 est.",
    is_estimate: true,
    expected_remainder: null,
    kind: "buy",
    note: null,
    stock_up: false,
    checked: false,
    checked_at: null,
    purchased: null,
    actual_price_cents: null,
    actual_price_display: null,
    ...overrides,
  };
}

const chicken = groceryItem();
const cabbage = groceryItem({
  id: 2,
  ingredient_id: 2,
  name: "green cabbage",
  category: "vegetable",
  to_buy: "1",
  estimated_cost_cents: 199,
  estimated_cost_display: "$1.99",
  is_estimate: false,
});
const tortillas = groceryItem({
  id: 3,
  ingredient_id: 3,
  name: "flour tortilla (Price Rite, 37 g)",
  category: "grain",
  store_id: 2,
  store_name: "Price Rite",
  to_buy: "1 × 20 ct bag",
  estimated_cost_cents: 199,
  estimated_cost_display: "$1.99",
});
const powder = groceryItem({
  id: 4,
  ingredient_id: 4,
  name: "protein powder, double chocolate",
  category: "supplement",
  store_id: 3,
  store_name: "Other",
  to_buy: "1 × 5 lb tub",
  estimated_cost_cents: 6250,
  estimated_cost_display: "$62.50 est.",
  stock_up: true,
});
const salt = groceryItem({
  id: 5,
  ingredient_id: 5,
  name: "salt",
  category: "spice",
  store_id: null,
  store_name: null,
  to_buy: "6 g",
  estimated_cost_cents: null,
  estimated_cost_display: null,
  kind: "staple",
});

function list(groups: GroceryList["groups"], groupBy: string): GroceryList {
  return {
    id: 9,
    plan_id: 7,
    status: "open",
    group_by: groupBy,
    checked_count: 0,
    to_check_count: 4,
    total_cents: 9995,
    total_display: "$99.95",
    regular_cents: 3745,
    stock_up_cents: 6250,
    cash_split_display: "$37.45 groceries + $62.50 stock-up",
    complete: true,
    unpriced: [],
    split: false,
    savings_cents: 0,
    split_threshold_cents: 500,
    note: null,
    groups,
  };
}

export const groceryByStore = list(
  [
    { kind: "store", key: "store:1", store_id: 1, store_name: "Stop & Shop", subtotal_cents: 1546, subtotal_display: "$15.46", items: [chicken, cabbage] },
    { kind: "store", key: "store:2", store_id: 2, store_name: "Price Rite", subtotal_cents: 199, subtotal_display: "$1.99", items: [tortillas] },
    { kind: "stock_up", key: "stock_up:x", store_id: null, store_name: "Also buy this week (stock-up)", subtotal_cents: 6250, subtotal_display: "$62.50", items: [powder] },
    { kind: "staple", key: "staple:x", store_id: null, store_name: "Check you have", subtotal_cents: 0, subtotal_display: "$0.00", items: [salt] },
  ],
  "store",
);

export const groceryByCategory = list(
  [
    { kind: "category", key: "category:Protein", store_id: null, store_name: "Protein", subtotal_cents: 1347, subtotal_display: "$13.47", items: [chicken] },
    { kind: "category", key: "category:Vegetable", store_id: null, store_name: "Vegetable", subtotal_cents: 199, subtotal_display: "$1.99", items: [cabbage] },
    { kind: "category", key: "category:Grain", store_id: null, store_name: "Grain", subtotal_cents: 199, subtotal_display: "$1.99", items: [tortillas] },
    { kind: "stock_up", key: "stock_up:x", store_id: null, store_name: "Also buy this week (stock-up)", subtotal_cents: 6250, subtotal_display: "$62.50", items: [powder] },
    { kind: "staple", key: "staple:x", store_id: null, store_name: "Check you have", subtotal_cents: 0, subtotal_display: "$0.00", items: [salt] },
  ],
  "category",
);

export function recipe(overrides: Partial<RecipeVersion> = {}): RecipeVersion {
  return {
    version_id: 3,
    recipe_id: 3,
    version_number: 1,
    title: "Chicken over rice with garlic yogurt",
    description: "Weeknight meal prep.",
    badge: "draft",
    origin: "seed",
    meal_slots: ["lunch", "dinner"],
    mood: "medium",
    cuisine: null,
    flavor_tags: [],
    equipment: ["stovetop", "oven"],
    freezer_friendly: true,
    base_servings: 4,
    portions: 4,
    portion_size: "normal",
    active_minutes: 30,
    total_minutes: 55,
    time_note: "",
    lines: [
      {
        ingredient_id: 1,
        name: "chicken thigh, boneless skinless",
        display: "680 g chicken thigh, boneless skinless",
        amount_display: "680 g",
        portion_note: "170 g per portion · 680 g for the batch of 4",
        preparation: "cubed",
        optional: false,
      },
    ],
    steps: [
      { section: "prep", text: "Cut the chicken into 1-inch pieces.", duration_minutes: null, appliance_temp_f: null, safety_note: null, added_by_app: false },
      {
        section: "oven",
        text: "Roast at 425°F for 20 minutes.",
        duration_minutes: 20,
        appliance_temp_f: 425,
        safety_note: "Cook chicken to 165°F (poultry).",
        added_by_app: false,
      },
      { section: "reheating", text: "Reheat leftovers until they reach 165°F throughout.", duration_minutes: null, appliance_temp_f: null, safety_note: "Reheat leftovers to 165°F.", added_by_app: true },
    ],
    per_container: "About 350 g per container",
    labels: ["High in protein"],
    heme_note: "The heme share of iron is an estimate.",
    per_portion: {
      kcal: 560,
      nutrients: [
        { code: "protein_g", display_name: "Protein", unit: "g", amount: "42.0", complete: true, missing_from: [], label: null },
        { code: "iron_mg", display_name: "Iron", unit: "mg", amount: "2.10", complete: true, missing_from: [], label: null },
      ],
      heme_iron: { heme_mg: "0.84", non_heme_mg: "1.26", label: "estimated" },
    },
    costs: [
      {
        store_id: 1,
        store_name: "Stop & Shop",
        total_cents: 1240,
        per_portion_cents: 310,
        complete: true,
        unpriced: [],
        staples_not_costed: [],
        uses_estimates: true,
      },
    ],
    incomplete_reasons: [],
    change_summary: null,
    created_at: "2026-10-08T12:00:00Z",
    dish_category: "bowl",
    is_favorite: false,
    is_saved: false,
    steps_ready: true,
    search_context: null,
    ...overrides,
  };
}

// ---------------- step 2b.4: the meal-now flow ----------------
export function suggestion(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    version_id: 21,
    recipe_id: 11,
    title: "Everyday chicken curry",
    dish_category: "curry",
    badges: [],
    steps_ready: true,
    portions: 1,
    portion_size: "normal",
    portions_display: "1 portion",
    numbers: ["540 kcal", "41 g protein", "35 min", "$2.10 a portion est.", "$1.29 est. to buy today"],
    uses: ["chicken thigh, boneless skinless", "spinach"],
    could_buy: [
      { ingredient_id: 7, name: "chickpeas", cost_cents: 129, cost_display: "$1.29 est.", store: "Stop & Shop", is_estimate: true, display: "chickpeas $1.29 est. (Stop & Shop)" },
    ],
    missing: [
      {
        ingredient_id: 8,
        name: "lemon",
        kind: "missing",
        substitute: { ingredient_id: 9, name: "lime juice", amount_display: "2 tbsp", you_have: true, note: null },
        buy: null,
        display: "lemon → lime juice (you have it)",
      },
    ],
    swaps: [
      {
        ingredient_id: 10,
        name: "yellow onion",
        substitute: { ingredient_id: 11, name: "red onion", amount_display: "1", you_have: true, note: null },
        display: "Swap: red onion instead of yellow onion (you have it)",
      },
    ],
    why: ["ready in 35 min"],
    score: "1.25",
    good_match: true,
    section: "match",
    ...overrides,
  };
}

export function cookHome(overrides: Partial<CookHome> = {}): CookHome {
  return {
    last: [
      {
        mode: "now",
        search_id: 5,
        summary: "A meal now · Dinner for 1 · Quick (30 min) · + chickpeas (could buy)",
        answers: { schema_version: 1, mode: "now", goals: ["quick"], time_limit_minutes: 30, pantry: [], extras: [{ ingredient_id: 7, status: "could_buy" }], allow_llm: true },
        extras: [{ ingredient_id: 7, name: "chickpeas", status: "could_buy" }],
      },
    ],
    today: null,
    favorites: [{ recipe_id: 11, version_id: 21, title: "Everyday chicken curry", dish_category: "curry" }],
    favorites_count: 1,
    later: [],
    later_count: 0,
    portions: 2,
    portion_size: "normal",
    ...overrides,
  };
}

export function lot(overrides: Partial<InventoryLot> = {}): InventoryLot {
  return {
    id: 31,
    ingredient_id: 1,
    name: "chicken thigh, boneless skinless",
    product_id: null,
    quantity: "907.185",
    unit: "g",
    display: "2 lb",
    location: "fridge",
    acquired_on: "2026-10-09",
    opened_on: null,
    expires_on: null,
    expiry_is_estimate: true,
    status: "active",
    notes: null,
    created_at: "2026-10-09T12:00:00Z",
    quantity_is_estimate: false,
    container: null,
    state: "allowed",
    has_versions: false,
    ...overrides,
  };
}

type FormFixture = AddOptions["forms"][number];
const NO_UNITS: FormFixture["custom_units"] = [];

/** GET /ingredients/{id}/add-options for frozen cauliflower: two forms, each with its package sizes. */
export function cauliflowerOptions(): AddOptions {
  return {
    ingredient_id: 61,
    name: "cauliflower, frozen",
    state: "allowed",
    message: null,
    versions: null,
    food: "Cauliflower",
    selected_form: "frozen",
    forms: [
      {
        form: "fresh",
        label: "Fresh head",
        ingredient_id: 60,
        name: "cauliflower",
        location: "fridge",
        state: "allowed",
        presets: [
          { key: "small", label: "small head (about 1.5 lb)", quantity: "680.389", unit: "g", container: "head", default: false, is_estimate: true },
          { key: "medium", label: "medium head (about 2 lb)", quantity: "907.185", unit: "g", container: "head", default: true, is_estimate: true },
        ],
        custom_units: NO_UNITS,
      },
      {
        form: "frozen",
        label: "Frozen florets",
        ingredient_id: 61,
        name: "cauliflower, frozen",
        location: "freezer",
        state: "allowed",
        presets: [
          { key: "10oz", label: "10 oz bag", quantity: "283.495", unit: "g", container: "bag", default: false, is_estimate: true },
          { key: "12oz", label: "12 oz bag", quantity: "340.194", unit: "g", container: "bag", default: true, is_estimate: true },
          { key: "16oz", label: "16 oz bag", quantity: "453.592", unit: "g", container: "bag", default: false, is_estimate: true },
        ],
        custom_units: [
          { unit: "lb", label: "lb", step: "0.25", start: "0.75" },
          { unit: "oz", label: "oz", step: "1", start: "12" },
        ],
      },
    ],
  };
}

/** Pepperoni: held, with its versions (J4). */
export function pepperoniOptions(): AddOptions {
  return {
    ingredient_id: 70,
    name: "pepperoni",
    state: "held",
    message: "Pepperoni is held: it may contain beef. Pick the version on its label.",
    food: null,
    selected_form: "as_is",
    forms: [{ form: "as_is", label: "pepperoni", ingredient_id: 70, name: "pepperoni", location: "fridge", state: "held", presets: [], custom_units: NO_UNITS }],
    versions: {
      question: "Which pepperoni is it?",
      guidance: "Check the label: the ingredients list says which meats it has.",
      choices: [
        { key: "pork_beef", label: "Pork + beef", ingredient_id: 71, name: "pepperoni, pork and beef", state: "excluded", note: "Off your list: it contains beef", nutrition_estimated: false },
        { key: "pork", label: "Pork only", ingredient_id: 72, name: "pepperoni, pork", state: "capped", note: "Allowed; counts toward your limit for pork as a meal component (1 meal a week)", nutrition_estimated: true },
        { key: "turkey", label: "Turkey", ingredient_id: 73, name: "pepperoni, turkey", state: "allowed", note: "Allowed", nutrition_estimated: false },
        { key: "chicken", label: "Chicken", ingredient_id: 74, name: "pepperoni, chicken", state: "allowed", note: "Allowed", nutrition_estimated: true },
        { key: "not_sure", label: "Not sure", ingredient_id: null, name: null, state: "held", note: "Stays held until you check the label", nutrition_estimated: false },
      ],
    },
  };
}

export function turkeyPepperoniOptions(): AddOptions {
  return {
    ingredient_id: 73,
    name: "pepperoni, turkey",
    state: "allowed",
    message: null,
    versions: null,
    food: null,
    selected_form: "as_is",
    forms: [
      {
        form: "as_is",
        label: "pepperoni, turkey",
        ingredient_id: 73,
        name: "pepperoni, turkey",
        location: "fridge",
        state: "allowed",
        presets: [
          { key: "5oz", label: "5 oz pack", quantity: "141.748", unit: "g", container: "pack", default: true, is_estimate: true },
          { key: "8oz", label: "8 oz pack", quantity: "226.796", unit: "g", container: "pack", default: false, is_estimate: true },
        ],
        custom_units: [{ unit: "oz", label: "oz", step: "1", start: "5" }],
      },
    ],
  };
}

export function batchDetail(overrides: Partial<BatchDetail> = {}): BatchDetail {
  return {
    id: 44,
    plan_id: 9,
    status: "planned",
    cook_on: "2026-10-10",
    portions: 1,
    portions_to_freeze: 0,
    portion_size: "normal",
    planned_minutes: 30,
    meals: [],
    lines: [{ ingredient_id: 1, name: "chicken thigh, boneless skinless", display: "6 oz", preparation: "cubed", optional: false, adjustment: null } as BatchDetail["lines"][number]],
    package_notes: [],
    freeze_notes: [],
    recipe: recipe(),
    pantry_notes: [{ ingredient_id: 1, name: "chicken thigh, boneless skinless", note: "uses 6 oz, about a quarter of your pack · 1.6 lb left after" }],
    ...overrides,
  };
}
