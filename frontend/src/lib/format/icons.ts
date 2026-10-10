// Emoji for dish categories, meals, goals and modes (FLOW_SPEC §4.4, §6, §7). Display only: the dish category
// itself comes from the server's classifier. Every emoji is shown with a text label or an aria-label.

export type IconEntry = { emoji: string; label: string };

export const DISH_ICONS: Record<string, IconEntry> = {
  drink: { emoji: "🥤", label: "Drink" },
  dessert: { emoji: "🍮", label: "Dessert" },
  oats: { emoji: "🥣", label: "Oats" },
  eggs: { emoji: "🍳", label: "Eggs" },
  wrap: { emoji: "🌯", label: "Wrap" },
  sandwich: { emoji: "🥪", label: "Sandwich" },
  soup: { emoji: "🍲", label: "Soup" },
  curry: { emoji: "🍛", label: "Curry" },
  pasta: { emoji: "🍝", label: "Pasta" },
  salad: { emoji: "🥗", label: "Salad" },
  bowl: { emoji: "🍚", label: "Bowl" },
  roast: { emoji: "🍗", label: "Roast" },
  snack: { emoji: "🥜", label: "Snack" },
  other: { emoji: "🍽️", label: "Meal" },
};

export function dishIcon(category: string | null | undefined): IconEntry {
  return DISH_ICONS[category ?? "other"] ?? (DISH_ICONS.other as IconEntry);
}

export const SLOT_ICONS: Record<string, IconEntry> = {
  breakfast: { emoji: "🥣", label: "Breakfast" },
  lunch: { emoji: "🥪", label: "Lunch" },
  dinner: { emoji: "🍽️", label: "Dinner" },
  protein_dessert: { emoji: "🍮", label: "Protein dessert" },
  snack: { emoji: "🥜", label: "Snack" },
  drink: { emoji: "🥤", label: "Drink" },
};

/** The meal tiles in the order onboarding and Settings show them. */
export const SLOT_ORDER = ["breakfast", "lunch", "dinner", "protein_dessert", "snack", "drink"] as const;

export type GoalKey = "protein" | "carb" | "cheap" | "quick" | "iron" | "low_calorie";

export const GOAL_ICONS: Record<GoalKey, IconEntry> = {
  protein: { emoji: "🍗", label: "High protein" },
  carb: { emoji: "🍚", label: "High carb" },
  cheap: { emoji: "🪙", label: "Cheap" },
  quick: { emoji: "⏱️", label: "Quick" },
  iron: { emoji: "🥬", label: "Iron rich" },
  low_calorie: { emoji: "🪶", label: "Low calorie" },
};

export const MODE_ICONS = {
  now: { emoji: "🍳", label: "A meal now" },
  prep: { emoji: "🍱", label: "Meal prep" },
} as const;

export const TAB_ICONS = {
  cook: "🍳",
  grocery: "🛒",
  pantry: "🥫",
  settings: "⚙️",
} as const;
