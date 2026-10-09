import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { plan } from "@/test/fixtures";

import { DayList } from "./DayList";
import { PlanNotices, WeekSummary } from "./WeekSummary";

describe("WeekSummary", () => {
  it("shows the PRD §25 summary from the server's numbers and display strings", () => {
    render(<WeekSummary plan={plan()} />);
    const summary = screen.getByRole("region", { name: "Week summary" });
    expect(within(summary).getByRole("heading", { name: "Week of Oct 12" })).toBeInTheDocument();
    expect(summary).toHaveTextContent("12,430 / 12,600 kcal");
    expect(summary).toHaveTextContent("High protein + Iron rich");
    expect(summary).toHaveTextContent("~116.0 g/day (target 100 g)");
    expect(summary).toHaveTextContent("Budget $42.00");
    expect(summary).toHaveTextContent("$38.70");
    expect(summary).toHaveTextContent("$34.10");
    expect(summary).toHaveTextContent("$1.20");
    expect(summary).toHaveTextContent("~3 h 30 min hands-on");
    expect(summary).toHaveTextContent("28");
  });

  it("says when the cost is incomplete and describes inventory mode", () => {
    const p = plan({ planning_mode: "inventory", purchase_limit_cents: 0 });
    p.costs = { ...p.costs, complete: false };
    render(<WeekSummary plan={p} />);
    expect(screen.getByText("Cook from what you have")).toBeInTheDocument();
    expect(screen.getByText(/unpriced items/)).toBeInTheDocument();
  });

  it("shows freeze instructions, warnings and notes", () => {
    const p = plan({
      freeze: [
        {
          ingredient_id: 1,
          name: "chicken thigh",
          amount: "600 g",
          freeze_on: "2026-10-12",
          use_on: "2026-10-15",
          thaw_on: "2026-10-14",
          recipe: "Curry",
          source: "purchase",
          message: "Freeze 600 g chicken thigh on shopping day",
        },
      ],
      warnings: [{ code: "EXPECTED_WASTE", message: "spinach: likely to spoil" }],
      notes: ["Recipe generation stopped early"],
    });
    render(<PlanNotices plan={p} />);
    expect(screen.getByText(/Freeze 600 g chicken thigh/)).toBeInTheDocument();
    expect(screen.getByText("spinach: likely to spoil")).toBeInTheDocument();
    expect(screen.getByText("Recipe generation stopped early")).toBeInTheDocument();
  });

  // (the export build adds the trailing slash: trailingSlash in next.config.ts)
  it("lists the days, links meals to their cook batch and labels leftovers days", () => {
    render(<DayList plan={plan()} />);
    expect(screen.getByRole("link", { name: "Mon Oct 12" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/day\/?\?plan=7&date=2026-10-12$/),
    );
    expect(screen.getByRole("link", { name: /Chicken over rice/ })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/recipe\/?\?batch=11$/),
    );
    expect(screen.getByText("Leftovers day")).toBeInTheDocument();
  });
});
