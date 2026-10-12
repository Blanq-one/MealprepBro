// The plan view's order and its remembered view (FLOW_SPEC C6, H4): Today first, then the following days; days
// before today fold into "Earlier in this plan". Dates are "YYYY-MM-DD", so they compare as strings.
import type { Day } from "@/lib/api/types";

export type DayOrder = { upcoming: Day[]; earlier: Day[] };

/** Today and the days after it, then the days before today. A plan that ended has only earlier days. */
export function orderDays(days: readonly Day[], today: string): DayOrder {
  return {
    upcoming: days.filter((d) => d.day >= today),
    earlier: days.filter((d) => d.day < today),
  };
}

export type PlanTab = "recipes" | "shopping";
export const VIEW_KEY = "mealbro.plan.view";

/** Recipes | Shopping list: the choice is remembered on this device (C6). */
export function readPlanTab(storage: Pick<Storage, "getItem"> | null = safeLocal()): PlanTab {
  try {
    return storage?.getItem(VIEW_KEY) === "shopping" ? "shopping" : "recipes";
  } catch {
    return "recipes";
  }
}

export function savePlanTab(tab: PlanTab, storage: Pick<Storage, "setItem"> | null = safeLocal()): void {
  try {
    storage?.setItem(VIEW_KEY, tab);
  } catch {
    // storage blocked: the choice lasts while this page is open
  }
}

function safeLocal(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}
