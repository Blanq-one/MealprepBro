import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PlanStreamEvent } from "@/lib/api/types";
import { weekDays, withOverrides } from "@/lib/plan/overrides";
import { recipe } from "@/test/fixtures";

import { PlanFailure } from "./PlanProgress";
import { RecipeView } from "./RecipeView";

const short = "Your inventory doesn't cover this week. The smallest top-up that makes a plan is about $36.20.";

function failure(): PlanStreamEvent {
  return {
    event: "result",
    run_id: 3,
    elapsed_s: 4,
    status: "infeasible",
    notes: [],
    problem: {
      type: "about:blank",
      status: 422,
      title: "No plan fits this week",
      detail: short, // the same words as the diagnostic: shown once
      diagnostics: [
        { code: "INVENTORY_SHORT", message: short, amount: 3620, suggested_cents: 3700, items: ["chicken thigh about 2 lb ($8.98)", "rice about 5 lb ($4.99)"] },
        { code: "INVENTORY_SHORT", message: short, amount: 3620, suggested_cents: 3700 },
      ],
    },
  } as unknown as PlanStreamEvent;
}

describe("no plan fits (2b.4 approval, B)", () => {
  it("says it once, in plain words, with buttons for the fix and the items behind a tap", async () => {
    const onTopUp = vi.fn();
    const onShop = vi.fn();
    render(<PlanFailure event={failure()} actions={{ onTopUp, onShop }} />);
    expect(screen.getAllByText(short)).toHaveLength(1);
    expect(screen.queryByText(/--topup/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Allow a $37 top-up" }));
    expect(onTopUp).toHaveBeenCalledWith(3700);
    await userEvent.click(screen.getByRole("button", { name: "Switch to shopping" }));
    expect(onShop).toHaveBeenCalled();
    expect(screen.getByText("chicken thigh about 2 lb ($8.98)")).not.toBeVisible();
    await userEvent.click(screen.getByText("See what it would buy"));
    expect(screen.getByText("chicken thigh about 2 lb ($8.98)")).toBeVisible();
  });
});

describe("no plan fits for time or mood (2b.3b approval, P4)", () => {
  const time = "Monday needs 50 minutes of hands-on cooking; you set 45.";
  const mood = "6 recipes are fancy and your cook days are set to medium.";
  const event = {
    event: "result",
    run_id: 4,
    elapsed_s: 9,
    status: "infeasible",
    notes: [],
    problem: {
      type: "about:blank",
      status: 422,
      title: "No plan fits this week",
      detail: `${time} ${mood}`,
      diagnostics: [
        { code: "COOK_TIME_SHORT", message: time, day: "2026-10-12", amount: 5, suggested_minutes: 50 },
        { code: "RECIPES_LEFT_OUT", message: mood, amount: 6, mood: "fancy" },
        { code: "COOK_TIME_SHORT", message: time, day: "2026-10-12", amount: 5, suggested_minutes: 50 },
      ],
    },
  } as unknown as PlanStreamEvent;

  it("says each problem once, in plain words, with a button for each fix", async () => {
    const onMinutes = vi.fn();
    const onMood = vi.fn();
    render(<PlanFailure event={event} actions={{ onMinutes, onMood }} />);
    expect(screen.getAllByText(time)).toHaveLength(1);
    expect(screen.getAllByText(mood)).toHaveLength(1);
    expect(screen.queryByText(/;\s*\./)).toBeNull(); // no stray punctuation
    await userEvent.click(screen.getByRole("button", { name: "Allow 50 min on Monday" }));
    expect(onMinutes).toHaveBeenCalledWith("2026-10-12", 50);
    await userEvent.click(screen.getByRole("button", { name: "Use simpler recipes" }));
    expect(onMood).toHaveBeenCalledWith("2026-10-12", "simple");
    await userEvent.click(screen.getByRole("button", { name: "Allow fancy recipes" }));
    expect(onMood).toHaveBeenCalledWith(null, "fancy");
  });

  it("a fix changes only this plan's days, a later change winning", () => {
    const one = withOverrides([], [{ day: "2026-10-12", cook_minutes: 50 }]);
    const two = withOverrides(one, [{ day: "2026-10-12", mood: "simple" }, { day: "2026-10-13", mood: "simple" }]);
    expect(two).toEqual([
      { day: "2026-10-12", cook_minutes: 50, mood: "simple" },
      { day: "2026-10-13", mood: "simple" },
    ]);
    expect(weekDays("2026-10-12")).toEqual(["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"]);
  });
});

describe("recipe amounts per portion and for the batch (2b.4 approval, A1)", () => {
  it("shows each line's amount once, then the server's per-portion note", () => {
    render(<RecipeView recipe={recipe()} />);
    expect(screen.getByText("680 g")).toBeInTheDocument();
    expect(screen.getByText("170 g per portion · 680 g for the batch of 4")).toBeInTheDocument();
    expect(screen.queryByText(/680 g chicken thigh/)).toBeNull(); // the name isn't printed twice
  });
});
