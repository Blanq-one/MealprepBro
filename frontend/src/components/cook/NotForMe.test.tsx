import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MealRow } from "@/components/plan/PlanView";
import { HiddenRecipesEditor } from "@/components/settings/HiddenRecipes";
import { settingsGroups } from "@/components/settings/SettingsList";
import { mockApi } from "@/test/api";
import { meal, settingsOut } from "@/test/fixtures";

import { HIDDEN_NOTE, NotForMe } from "./NotForMe";

afterEach(() => vi.unstubAllGlobals());

describe("Not for me (F24)", () => {
  it("on a recipe page: hides it from every future suggestion and plan, with Undo", async () => {
    const calls = mockApi(() => ({ status: 204 }));
    render(<NotForMe recipeId={11} title="Everyday chicken curry" online />);
    await userEvent.click(screen.getByRole("button", { name: "Not for me: never suggest Everyday chicken curry again" }));
    expect(await screen.findByText(HIDDEN_NOTE)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Undo: show Everyday chicken curry again" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Not for me/ })).toBeInTheDocument());
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(["PUT /api/v1/recipes/11/hidden", "DELETE /api/v1/recipes/11/hidden"]);
  });

  it("a recipe you already hid says so; offline it needs a connection", () => {
    render(<NotForMe recipeId={11} title="Everyday chicken curry" hidden online={false} />);
    expect(screen.getByText(HIDDEN_NOTE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Undo/ })).toBeDisabled();
    expect(screen.getByText("Needs a connection")).toBeInTheDocument();
  });

  it("on a plan meal row, separate from opening the recipe: the sheet hides it and records the plan meal", async () => {
    const calls = mockApi(() => ({ status: 204 }));
    render(
      <ul>
        <MealRow meal={meal({ recipe_id: 3, title: "Chicken over rice", plan_meal_id: 101 })} online />
      </ul>,
    );
    expect(screen.getByRole("link", { name: /Chicken over rice/ })).toHaveAttribute("href", expect.stringMatching(/batch=11/));
    await userEvent.click(screen.getByRole("button", { name: "More for Chicken over rice" }));
    const sheet = screen.getByRole("dialog", { name: "Chicken over rice" });
    expect(within(sheet).getByText(/This plan keeps it/)).toBeInTheDocument();
    await userEvent.click(within(sheet).getByRole("button", { name: /Not for me/ }));
    expect(await within(sheet).findByText(HIDDEN_NOTE)).toBeInTheDocument();
    expect(calls).toEqual([{ method: "PUT", path: "/api/v1/recipes/3/hidden?plan_meal=101", body: undefined }]);
  });
});

describe("Settings, Hidden recipes", () => {
  const hidden = [
    { recipe_id: 11, version_id: 21, title: "Everyday chicken curry", kind: "dish", dish_category: "curry", hidden_at: "2026-10-12T10:00:00Z" },
    { recipe_id: 90, version_id: 91, title: "Spiced chicken wrap", kind: "assembly", dish_category: "wrap", hidden_at: "2026-10-11T10:00:00Z" },
  ];

  it("the row counts them and opens the list", () => {
    const diet = settingsGroups(settingsOut(), {}, 2).find((g) => g.title === "Diet");
    expect(diet?.rows.find((r) => r.field === "hidden_recipes")).toMatchObject({ label: "Hidden recipes", value: "2 hidden" });
    expect(settingsGroups(settingsOut(), {}, 0).flatMap((g) => g.rows).find((r) => r.field === "hidden_recipes")?.value).toBe("None");
  });

  it("lists dishes, prep items and meals, each with Show again", async () => {
    const calls = mockApi((call) => (call.method === "GET" ? { body: hidden } : { status: 204 }));
    render(<HiddenRecipesEditor online onDone={() => undefined} />);
    const list = await screen.findByRole("list", { name: "Hidden recipes" });
    expect(within(list).getByText("Everyday chicken curry")).toBeInTheDocument();
    expect(within(list).getByText("Meal")).toBeInTheDocument(); // an assembly
    await userEvent.click(within(list).getAllByRole("button", { name: "Show again" })[0] as HTMLElement);
    expect(await screen.findByText("Everyday chicken curry can come up again.")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Hidden recipes" })).getAllByRole("listitem")).toHaveLength(1);
    expect(calls.at(-1)).toMatchObject({ method: "DELETE", path: "/api/v1/recipes/11/hidden" });
  });

  it("nothing hidden says so", async () => {
    mockApi(() => ({ body: [] }));
    render(<HiddenRecipesEditor online onDone={() => undefined} />);
    expect(await screen.findByText(/Nothing hidden/)).toBeInTheDocument();
  });
});
