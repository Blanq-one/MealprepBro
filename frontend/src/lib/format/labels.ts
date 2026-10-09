// Display labels for API enums and plain numbers. Formatting only: every value comes from the server.

const SLOT_LABELS: Record<string, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
  snack: "Snack",
  protein_dessert: "Protein dessert",
  drink: "Drink",
};

const FOCUS_LABELS: Record<string, string> = {
  protein: "High protein",
  carb: "Carb rich",
  iron: "Iron rich",
  balanced: "Balanced",
  fiber: "Fiber rich",
  lower_fat: "Lower fat",
  satiety: "Higher satiety",
  vegetable: "More vegetables",
};

export function slotLabel(slot: string): string {
  return SLOT_LABELS[slot] ?? humanize(slot);
}

export function focusLabel(focus: string | null | undefined): string {
  if (!focus) return "";
  return FOCUS_LABELS[focus] ?? humanize(focus);
}

export function humanize(value: string): string {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** 12420 -> "12,420". */
export function grouped(value: number): string {
  return value.toLocaleString("en-US");
}

/** 210 -> "3 h 30 min", 45 -> "45 min". */
export function minutesLabel(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}
