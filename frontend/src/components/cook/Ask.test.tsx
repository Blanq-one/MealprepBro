import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AlwaysHaveOption, InventoryLot } from "@/lib/api/types";
import { emptyDraft, type MealNowDraft } from "@/lib/cook/answers";
import { mockApi } from "@/test/api";
import { cookHome, lot } from "@/test/fixtures";

import { GoalsStep, PICK_A_MEAL } from "./GoalsStep";
import { alwaysHaveLine, HaveStep } from "./HaveStep";

const staples: AlwaysHaveOption[] = ["rice", "olive oil", "salt", "black pepper", "garlic"].map((name, i) => ({ ingredient_id: 100 + i, slug: name, name, category: "pantry", common: true, selected: true }));

function pantry(lots: InventoryLot[]) {
  return mockApi((call) => {
    if (call.path === "/api/v1/inventory") return { body: lots };
    if (call.path === "/api/v1/settings/always-have") return { body: staples };
    if (call.path === "/api/v1/inventory/quick-picks") return { body: [] };
    return undefined;
  });
}

function Have({ initial = emptyDraft(), online = true, onDraft }: { initial?: MealNowDraft; online?: boolean; onDraft?: (d: MealNowDraft) => void }) {
  const [draft, setDraft] = useState(initial);
  return (
    <HaveStep
      draft={draft}
      onChange={(d) => {
        setDraft(d);
        onDraft?.(d);
      }}
      online={online}
      last={cookHome().last[0] ?? null}
      onBack={() => undefined}
      onFind={() => undefined}
    />
  );
}

describe("C2 goals", () => {
  it("the meal is a visible choice with nothing preselected, never guessed from the clock (M9)", async () => {
    const onNext = vi.fn();
    function Goals() {
      const [draft, setDraft] = useState(emptyDraft());
      return <GoalsStep draft={draft} householdSize={2} onChange={setDraft} onBack={() => undefined} onNext={onNext} />;
    }
    render(<Goals />);
    const meals = screen.getByRole("group", { name: "Meal" });
    expect(within(meals).getAllByRole("button").map((b) => b.textContent?.replace(/[^A-Za-z]/g, ""))).toEqual(["Breakfast", "Lunch", "Dinner", "Snack", "Dessert"]);
    expect(within(meals).queryByRole("button", { pressed: true })).toBeNull();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(PICK_A_MEAL);
    await userEvent.click(within(meals).getByRole("button", { name: /Dinner/ }));
    expect(within(meals).getByRole("button", { name: /Dinner/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /People: 2/ })).toBeInTheDocument(); // your household size
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onNext).toHaveBeenCalled();
  });

  it("Quick shows Ready in; a mood tapped again goes back to your usual", async () => {
    function Goals() {
      const [draft, setDraft] = useState(emptyDraft());
      return <GoalsStep draft={draft} householdSize={1} onChange={setDraft} onBack={() => undefined} onNext={() => undefined} />;
    }
    render(<Goals />);
    expect(screen.queryByRole("group", { name: "Ready in" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Quick/ }));
    expect(screen.getByRole("button", { name: /Ready in: 30/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Fancy/ }));
    expect(screen.getByRole("button", { name: /Fancy/ })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: /Fancy/ }));
    expect(screen.getByText(/Not picked: today's usual from your cook schedule\. Recipes in your mood come first/)).toBeInTheDocument();
  });
});

describe("C3 what do you have", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("pantry items are on by default; turning one off keeps it out of this search", async () => {
    pantry([lot(), lot({ id: 32, ingredient_id: 2, name: "spinach", display: "10 oz", opened_on: "2026-10-09" })]);
    const onDraft = vi.fn();
    render(<Have onDraft={onDraft} />);
    const spinach = await screen.findByRole("switch", { name: "spinach" });
    expect(spinach).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("Open")).toBeInTheDocument();
    await userEvent.click(spinach);
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ off: [2] }));
    expect(screen.getByRole("switch", { name: "spinach" })).toHaveAttribute("aria-checked", "false");
  });

  it("Always have sits in one line; last time's extras are chips that add them back, not pre-selected", async () => {
    pantry([lot()]);
    const onDraft = vi.fn();
    render(<Have onDraft={onDraft} />);
    expect(await screen.findByText("Always have: rice, olive oil, salt and 2 more")).toBeInTheDocument();
    expect(alwaysHaveLine(["rice"])).toBe("Always have: rice");
    await userEvent.click(screen.getByRole("button", { name: "chickpeas · could buy" }));
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ extras: [{ ingredient_id: 7, name: "chickpeas", status: "could_buy" }] }));
    expect(screen.getByRole("button", { name: "Remove chickpeas · could buy" })).toBeInTheDocument();
  });

  it("a held lot can't be toggled and offers its versions", async () => {
    pantry([lot({ id: 33, ingredient_id: 70, name: "pepperoni", display: "6 oz", state: "held", has_versions: true })]);
    render(<Have />);
    expect(await screen.findByRole("switch", { name: "pepperoni" })).toBeDisabled();
    expect(screen.getByText("Held")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Which version?" })).toBeInTheDocument();
  });

  it("an empty pantry says so; offline, Find recipes needs a connection", async () => {
    pantry([]);
    render(<Have online={false} />);
    expect(await screen.findByText("Your pantry is empty. Add what you have, or skip and I'll show what to buy.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Find recipes" })).toBeDisabled();
    await waitFor(() => expect(screen.getAllByText("Needs a connection").length).toBeGreaterThan(0));
  });
});
