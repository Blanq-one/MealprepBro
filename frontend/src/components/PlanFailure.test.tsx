import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PlanStreamEvent } from "@/lib/api/types";
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

describe("recipe amounts per portion and for the batch (2b.4 approval, A1)", () => {
  it("shows each line's amount once, then the server's per-portion note", () => {
    render(<RecipeView recipe={recipe()} />);
    expect(screen.getByText("680 g")).toBeInTheDocument();
    expect(screen.getByText("170 g per portion · 680 g for the batch of 4")).toBeInTheDocument();
    expect(screen.queryByText(/680 g chicken thigh/)).toBeNull(); // the name isn't printed twice
  });
});
