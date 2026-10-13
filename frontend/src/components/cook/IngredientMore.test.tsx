import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecipeView } from "@/components/RecipeView";
import { PreferencesEditor } from "@/components/settings/DietEditors";
import { foodsValue } from "@/components/settings/SettingsList";
import type { LineOptions, PlanUpdate, RecipeEdit } from "@/lib/api/types";
import { mockApi } from "@/test/api";
import { plan, recipe, settingsOut } from "@/test/fixtures";

import { IngredientSheet, NEVER_NOTE } from "./IngredientMore";

function options(overrides: Partial<LineOptions> = {}): LineOptions {
  return {
    line_id: 21,
    ingredient_id: 5,
    name: "chicken thigh, boneless skinless",
    display: "600 g chicken thigh, boneless skinless",
    swaps: [
      { ingredient_id: 6, name: "chicken breast, boneless skinless", display: "560 g", numbers: ["−38 kcal", "+1.2 g protein", "+$0.31"], note: null, cooking_note: "Chicken breast, boneless skinless cooks differently from chicken thigh, boneless skinless: it may need more or less time, so cook it until it's done." },
    ],
    leave_out: { allowed: false, reason: "Only a garnish, an optional line, a seasoning or a small aromatic can be left out; this one carries the dish. Swap it instead.", numbers: [], warning: null },
    in_pantry: false,
    never_used: false,
    shopping: { plan_id: 5, list_id: 9, can_add: true, reason: null },
    ...overrides,
  };
}

function edited(overrides: Partial<RecipeEdit> = {}): RecipeEdit {
  return {
    version: recipe({ version_id: 30, your_version: true, change_summary: "Your version: chicken breast instead of chicken thigh" }),
    note: "Your version: chicken breast instead of chicken thigh",
    cooking_note: "Chicken breast cooks differently.",
    flagged_steps: [2],
    batch_id: 11,
    can_update_plan: true,
    plan_note: null,
    ...overrides,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("a line's ⋯ (AA5)", () => {
  it("shows Swap it with the change per portion, Leave it out's reason, I'm out of this and Never use this", async () => {
    const calls = mockApi((c) => {
      if (c.path.startsWith("/api/v1/recipe-versions/3/lines/21/options")) return { body: options() };
      if (c.path.endsWith("/add-to-list?batch=11")) return { body: { added: true, plan_id: 5, list_id: 9, message: "Added 1 × chicken thighs, 2 lb to your shopping list ($6.99)." } };
      if (c.path === "/api/v1/settings/ingredient-preferences/5") return c.method === "PUT" ? { body: settingsOut() } : { status: 204 };
      return undefined;
    });
    render(<IngredientSheet versionId={3} lineId={21} name="chicken thigh" batch={{ id: 11, planId: 5, cookOn: "2026-10-14" }} online onClose={() => undefined} onOpenVersion={() => undefined} />);
    const breast = await screen.findByRole("button", { name: "Swap to chicken breast, boneless skinless" });
    expect(breast).toHaveTextContent("560 g");
    expect(breast).toHaveTextContent("−38 kcal · +1.2 g protein · +$0.31 a portion");
    expect(breast).toHaveTextContent("cooks differently");
    expect(screen.getByText(/carries the dish/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Leave out/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Add to shopping list" }));
    expect(await screen.findByText("Added 1 × chicken thighs, 2 lb to your shopping list ($6.99).")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Never use chicken thigh" }));
    expect(await screen.findByText(NEVER_NOTE)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ preference: "exclude", reason: "Never use this" });
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(1);
    expect(calls[0]?.path).toBe("/api/v1/recipe-versions/3/lines/21/options?batch=11");
  });

  it("a line with a budget equivalent can be fixed to either side for this recipe (2b.6 approval, item 4)", async () => {
    const calls = mockApi((c) => {
      if (c.path.includes("/options")) return { body: options({ name: "tomato", display: "3 tomato", swaps: [], pair: { classic: "tomato", budget: "diced tomatoes, canned", budget_display: "360 ml diced tomatoes, canned" } }) };
      if (c.path.endsWith("/edits")) return { body: edited({ note: "Your version: always diced tomatoes instead of tomato", cooking_note: null, flagged_steps: [] }) };
      return undefined;
    });
    render(<IngredientSheet versionId={3} lineId={21} name="tomato" batch={{ id: 11, planId: 5, cookOn: "2026-10-14" }} online onClose={() => undefined} onOpenVersion={() => undefined} />);
    expect(await screen.findByRole("heading", { name: "Classic or budget" })).toBeInTheDocument();
    expect(screen.getByText(/whichever is cheaper at your stores: tomato \(the classic\) or 360 ml diced tomatoes, canned/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Always the classic: tomato" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Always the budget one: diced tomatoes, canned" }));
    expect(await screen.findByText(/always diced tomatoes instead of tomato/)).toBeInTheDocument();
    expect(calls.find((c) => c.path.endsWith("/edits"))?.body).toMatchObject({ line_id: 21, action: "use_budget", batch_id: 11 });
  });

  it("a line without one has no Classic or budget section", async () => {
    mockApi((c) => (c.path.includes("/options") ? { body: options() } : undefined));
    render(<IngredientSheet versionId={3} lineId={21} name="chicken thigh" online onClose={() => undefined} onOpenVersion={() => undefined} />);
    expect(await screen.findByRole("heading", { name: "Swap it" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Classic or budget" })).toBeNull();
  });

  it("a non-essential line can be left out, with the drop per portion and a warning", async () => {
    mockApi((c) => (c.path.includes("/options") ? { body: options({ name: "cilantro", leave_out: { allowed: true, reason: null, numbers: ["−1 kcal", "−0.1 g protein", "−$0.05"], warning: null }, swaps: [] }) } : undefined));
    render(<IngredientSheet versionId={3} lineId={21} name="cilantro" online onClose={() => undefined} onOpenVersion={() => undefined} />);
    expect(await screen.findByRole("button", { name: "Leave out cilantro" })).toBeInTheDocument();
    expect(screen.getByText("−1 kcal · −0.1 g protein · −$0.05 a portion")).toBeInTheDocument();
    expect(screen.getByText("Nothing from its group or role fits your rules.")).toBeInTheDocument();
  });

  it("a swap saves your version; from a plan meal, Also update this week's plan switches the batch", async () => {
    const update = { plan_id: 6, undo_plan_id: 5, message: "Updated this week's plan: Wed 14's Chicken curry uses your version.", also_changed: [], plan: plan({ id: 6, batches: [] }) } as PlanUpdate;
    update.plan.batches = [{ ...(plan().batches[0] ?? {}), id: 44, cook_on: "2026-10-14", recipe_version_id: 30 } as PlanUpdate["plan"]["batches"][number]];
    const calls = mockApi((c) => {
      if (c.path.includes("/options")) return { body: options() };
      if (c.path === "/api/v1/recipe-versions/3/edits") return { body: edited() };
      if (c.path === "/api/v1/plans/5/batches/11/use-version") return { body: update };
      return undefined;
    });
    const onPlanUpdated = vi.fn();
    const onOpenVersion = vi.fn();
    render(<IngredientSheet versionId={3} lineId={21} name="chicken thigh" batch={{ id: 11, planId: 5, cookOn: "2026-10-14" }} online onClose={() => undefined} onOpenVersion={onOpenVersion} onPlanUpdated={onPlanUpdated} />);
    await userEvent.click(await screen.findByRole("button", { name: "Swap to chicken breast, boneless skinless" }));
    expect(calls.find((c) => c.path.endsWith("/edits"))?.body).toEqual({ line_id: 21, batch_id: 11, ingredient_id: 6, action: "swap" });
    expect(await screen.findByText(/Your version: chicken breast instead of chicken thigh/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rewrite steps for this change" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Also update this week's plan" }));
    expect(onPlanUpdated).toHaveBeenCalledWith(update, 44);
    await userEvent.click(screen.getByRole("button", { name: "Open your version" }));
    expect(onOpenVersion).toHaveBeenCalledWith(30);
  });

  it("a cooked batch keeps its recipe: the plan note says so, with no update button", async () => {
    mockApi((c) => (c.path.includes("/options") ? { body: options() } : c.path.endsWith("/edits") ? { body: edited({ can_update_plan: false, plan_note: "Wed 14's batch is already cooked, so it keeps the recipe it was cooked with.", cooking_note: null }) } : undefined));
    render(<IngredientSheet versionId={3} lineId={21} name="chicken thigh" batch={{ id: 11, planId: 5, cookOn: "2026-10-14" }} online onClose={() => undefined} onOpenVersion={() => undefined} />);
    await userEvent.click(await screen.findByRole("button", { name: "Swap to chicken breast, boneless skinless" }));
    expect(await screen.findByText(/already cooked/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Also update this week's plan" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Rewrite steps for this change" })).toBeNull();
  });
});

describe("the recipe page for your version", () => {
  it("a ⋯ on each line, the Your version line and the flagged step", () => {
    const mine = recipe({
      your_version: true,
      change_summary: "Your version: chicken breast instead of chicken thigh",
      lines: [{ ingredient_id: 6, name: "chicken breast", display: "560 g chicken breast", preparation: null, optional: false, amount_display: "560 g", line_id: 21 }],
      steps: [{ section: "stovetop", text: "Sear the chicken breast.", duration_minutes: 8, appliance_temp_f: null, safety_note: null, added_by_app: false, flag: "Chicken breast cooks differently." }],
    });
    render(<RecipeView recipe={mine} lineAction={(line) => <button type="button">More for {line.name}</button>} />);
    expect(screen.getByTestId("your-version")).toHaveTextContent("Your version: chicken breast instead of chicken thigh");
    const lines = within(screen.getByRole("region", { name: "Ingredients" }));
    expect(lines.getByRole("button", { name: "More for chicken breast" })).toBeInTheDocument();
    expect(screen.getByTestId("step-flag")).toHaveTextContent("Your version: Chicken breast cooks differently.");
  });
});

describe("Settings, Foods I don't eat", () => {
  it("beef first, then your list with Allow again; dislikes use less", async () => {
    const calls = mockApi((c) => {
      if (c.path === "/api/v1/settings") return { body: { ...settingsOut(), preferences: [{ ingredient_id: 7, name: "cilantro", preference: "exclude", reason: "Never use this" }, { ingredient_id: 8, name: "mushrooms", preference: "dislike", reason: null }] } };
      if (c.path === "/api/v1/settings/ingredient-preferences/7") return { status: 204 };
      return undefined;
    });
    render(<PreferencesEditor onDone={() => undefined} online />);
    expect(await screen.findByRole("heading", { name: "Foods I don't eat" })).toBeInTheDocument();
    expect(screen.getByText("Beef")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Allow again: cilantro" }));
    expect(calls.some((c) => c.method === "DELETE" && c.path.endsWith("/7"))).toBe(true);
    expect(screen.getByRole("button", { name: "Remove: mushrooms" })).toBeInTheDocument();
    expect(foodsValue([{ name: "cilantro", preference: "exclude" }, { name: "mushrooms", preference: "dislike" }])).toBe("cilantro · use less: mushrooms");
    expect(foodsValue([])).toBe("None");
  });
});
