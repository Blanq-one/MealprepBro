import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TodayOut } from "@/lib/api/types";

import { TodayCard } from "./TodayCard";

function today(overrides: Partial<TodayOut> = {}): TodayOut {
  return {
    plan_id: 7,
    state: "today",
    message: null,
    day: "2026-10-12",
    meals: [{ slot: "lunch", title: "Chicken over rice", dish_category: "bowl", kcal: 560, from_freezer: false, cook_batch_id: 3, recipe_version_id: 4 }],
    cook_note: "Cook: Chicken over rice (4 portions)",
    hands_on_display: "45 min hands-on",
    ...overrides,
  };
}

describe("the Cook home Today card", () => {
  it("shows today's meals with their dish icons and what to cook today, from the API", () => {
    render(<TodayCard today={today()} />);
    expect(screen.getByRole("img", { name: "Bowl" })).toHaveTextContent("🍚");
    expect(screen.getByText("Chicken over rice")).toBeInTheDocument();
    expect(screen.getByText("Cook: Chicken over rice (4 portions) · 45 min hands-on")).toBeInTheDocument();
    // C6 opens at today (step 2b.7: the old day screen is retired)
    expect(screen.getByRole("link", { name: /Today/ })).toHaveAttribute("href", expect.stringMatching(/^\/cook\/plan\/?\?id=7&date=2026-10-12$/));
  });

  it("an assembled meal (no batch of its own) shows like any other", () => {
    render(<TodayCard today={today({ meals: [{ slot: "dinner", title: "Chicken curry with rice", dish_category: "curry", kcal: 640, from_freezer: false, cook_batch_id: null, recipe_version_id: 9 }] })} />);
    expect(screen.getByText("Chicken curry with rice")).toBeInTheDocument();
  });

  it("a day with nothing to cook says so", () => {
    render(<TodayCard today={today({ cook_note: "Nothing to cook, eating prepped meals", hands_on_display: null })} />);
    expect(screen.getByText("Nothing to cook, eating prepped meals")).toBeInTheDocument();
  });

  it("a plan that starts later or has ended says when", () => {
    const { rerender } = render(<TodayCard today={today({ state: "starts_later", message: "Your plan starts Monday", day: null, meals: [] })} />);
    expect(screen.getByText("Your plan starts Monday.")).toBeInTheDocument();
    rerender(<TodayCard today={today({ state: "ended", message: "Your plan ended Sunday", day: null, meals: [] })} />);
    expect(screen.getByText("Your plan ended Sunday.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open your plan" })).toHaveAttribute("href", expect.stringMatching(/^\/cook\/plan\/?\?id=7$/));
  });
});
