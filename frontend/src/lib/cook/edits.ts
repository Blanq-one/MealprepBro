// A line's ⋯ on recipe pages and plan meals (step 2b.6, AA5, AA8): its options, your-version edits, I'm out of
// this, Never use this, and Also update this week's plan. Display only: every number and line is the server's.
import { api } from "@/lib/api/client";
import type { AddToList, LineOptions, PlanSummary, PlanUpdate, RecipeEdit, RecipeEditBody, RecipeVersion } from "@/lib/api/types";

const batchQuery = (batchId?: number | null) => (batchId ? `?batch=${batchId}` : "");

export function lineOptions(versionId: number, lineId: number, batchId?: number | null): Promise<LineOptions> {
  return api<LineOptions>(`/api/v1/recipe-versions/${versionId}/lines/${lineId}/options${batchQuery(batchId)}`);
}

export function editLine(versionId: number, body: RecipeEditBody): Promise<RecipeEdit> {
  return api<RecipeEdit>(`/api/v1/recipe-versions/${versionId}/edits`, { method: "POST", json: body });
}

export function addToList(versionId: number, lineId: number, batchId?: number | null): Promise<AddToList> {
  return api<AddToList>(`/api/v1/recipe-versions/${versionId}/lines/${lineId}/add-to-list${batchQuery(batchId)}`, { method: "POST" });
}

/** Never use this: a Foods I don't eat entry (Settings), like beef. Allow again removes it. */
export async function neverUse(ingredientId: number, on: boolean): Promise<void> {
  if (on) await api<unknown>(`/api/v1/settings/ingredient-preferences/${ingredientId}`, { method: "PUT", json: { preference: "exclude", reason: "Never use this" } });
  else await api<void>(`/api/v1/settings/ingredient-preferences/${ingredientId}`, { method: "DELETE" });
}

export function applyVersionToPlan(planId: number, batchId: number, versionId: number): Promise<PlanUpdate> {
  return api<PlanUpdate>(`/api/v1/plans/${planId}/batches/${batchId}/use-version`, { method: "POST", json: { version_id: versionId } });
}

export function rewriteSteps(versionId: number): Promise<RecipeVersion> {
  return api<RecipeVersion>(`/api/v1/recipe-versions/${versionId}/rewrite-steps`, { method: "POST" });
}

/** After Also update this week's plan: the batch in the new plan version that uses your version. */
export function switchedBatch(plan: PlanSummary, cookOn: string, versionId: number): number | null {
  return plan.batches.find((b) => b.cook_on === cookOn && b.recipe_version_id === versionId)?.id ?? null;
}
