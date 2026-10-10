import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SavedRecipe } from "@/lib/api/types";
import { mockApi } from "@/test/api";

import { afterCookThis, RecipeActions } from "./RecipeActions";
import { SavedLists } from "./SavedLists";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));

function saved(overrides: Partial<SavedRecipe> = {}): SavedRecipe {
  return {
    recipe_id: 11,
    version_id: 21,
    title: "Everyday chicken curry",
    dish_category: "curry",
    badges: ["favorite"],
    steps_ready: true,
    portions: 1,
    portion_size: "normal",
    portions_display: "1 portion",
    numbers: ["540 kcal", "41 g protein"],
    uses: [],
    could_buy: [],
    missing: [],
    saved_at: "2026-10-09T12:00:00Z",
    ...overrides,
  } as SavedRecipe;
}

describe("C7 Saved lists", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    push.mockReset();
  });

  it("tapping ♥ on a favorite takes it off the list, with Undo", async () => {
    const calls = mockApi((call) => (call.path.startsWith("/api/v1/recipes/saved") ? { body: [saved()] } : { status: 204 }));
    render(<SavedLists list="favorites" onList={() => undefined} />);
    await userEvent.click(await screen.findByRole("button", { name: "Remove Everyday chicken curry from favorites" }));
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Removed Everyday chicken curry from favorites.");
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByRole("article")).toBeInTheDocument();
    await waitFor(() => expect(calls.filter((c) => c.method !== "GET").map((c) => `${c.method} ${c.path}`)).toEqual(["DELETE /api/v1/recipes/11/favorite", "PUT /api/v1/recipes/11/favorite"]));
  });

  it("an empty list says how to fill it", async () => {
    mockApi(() => ({ body: [] }));
    render(<SavedLists list="later" onList={() => undefined} />);
    expect(await screen.findByText("Tap 🔖 on anything you want to try later.")).toBeInTheDocument();
  });
});

describe("Cook this", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    push.mockReset();
  });

  it("saves a one-meal plan, then Buy first when there's something to buy, else cooking mode", async () => {
    const calls = mockApi((call) => (call.path === "/api/v1/cook/meals" ? { status: 201, body: { plan_id: 9, batch_id: 44, grocery_list_id: 3, buy_first: true, created: true } } : undefined));
    const recipe = { recipe_id: 11, title: "Curry", is_favorite: false, is_saved: false };
    render(<RecipeActions recipe={recipe} cook={{ meal: { version_id: 21, search_id: 5 } }} online />);
    await userEvent.click(screen.getByRole("button", { name: "Cook this" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/cook/buy/?batch=44&plan=9"));
    expect(calls[0]).toMatchObject({ method: "POST", path: "/api/v1/cook/meals", body: { version_id: 21, search_id: 5 } });
    expect(afterCookThis({ batch_id: 44, plan_id: 9, buy_first: false })).toBe("/cook/cooking/?batch=44");
  });

  it("for a plan batch it opens cooking mode; offline a new meal needs a connection", async () => {
    const recipe = { recipe_id: 11, title: "Curry", is_favorite: true, is_saved: false };
    const { rerender } = render(<RecipeActions recipe={recipe} cook={{ batchId: 44 }} online={false} />);
    await userEvent.click(screen.getByRole("button", { name: "Cook this" }));
    expect(push).toHaveBeenCalledWith("/cook/cooking/?batch=44");
    expect(screen.getByRole("button", { name: "Remove Curry from favorites" })).toHaveAttribute("aria-pressed", "true");
    rerender(<RecipeActions recipe={recipe} cook={{ meal: { version_id: 21 } }} online={false} />);
    expect(screen.getByRole("button", { name: "Cook this" })).toBeDisabled();
    expect(screen.getByText("Needs a connection")).toBeInTheDocument();
  });
});
