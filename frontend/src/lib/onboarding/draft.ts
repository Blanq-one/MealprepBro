// The onboarding draft (FLOW_SPEC §6): your answers stay on this device while you go (closing the app keeps
// them for next launch); "Start cooking" saves them with one PUT /settings.
import type { MealSlot, UserSettings } from "@/lib/api/types";

export type OnboardingDraft = {
  settings: UserSettings;
  pendingMeals: MealSlot[]; // meals you added that still need their calories
  newStores: string[]; // stores you typed in; created with POST /stores when you save
};

export const DRAFT_KEY = "mealbro.onboarding.draft";

export function loadDraft(): OnboardingDraft | null {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw) as Partial<OnboardingDraft> | null;
    if (!draft || typeof draft !== "object" || !draft.settings) return null;
    return { settings: draft.settings, pendingMeals: draft.pendingMeals ?? [], newStores: draft.newStores ?? [] };
  } catch {
    return null;
  }
}

export function saveDraft(draft: OnboardingDraft): void {
  try {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // storage blocked: the draft lasts while this page is open
  }
}

export function clearDraft(): void {
  try {
    window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    // nothing to clear
  }
}

export function newDraft(settings: UserSettings): OnboardingDraft {
  return { settings, pendingMeals: [], newStores: [] };
}

/** What POST /settings/preview can check before the new stores exist: the draft without them (and without
 * the store order at all when only new stores are picked; the saved order stands in until then). */
export function previewBody(draft: OnboardingDraft): Partial<UserSettings> {
  const { store_order, ...rest } = draft.settings;
  const known = store_order.filter((s) => !draft.newStores.includes(s));
  return known.length ? { ...rest, store_order: known } : rest;
}
