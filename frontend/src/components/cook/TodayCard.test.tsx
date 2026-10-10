import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { plan } from "@/test/fixtures";

import { todayInPlan, TodayView } from "./TodayCard";

describe("the Cook home Today card", () => {
  it("shows today's meals with their dish icons and what to cook today, from the API", () => {
    render(<TodayView plan={plan()} today="2026-10-12" />);
    expect(screen.getByRole("img", { name: "Bowl" })).toHaveTextContent("🍚");
    expect(screen.getByText("Chicken over rice")).toBeInTheDocument();
    expect(screen.getByText("Cook: Chicken over rice (4 portions) · 45 min hands-on")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Today/ })).toHaveAttribute("href", expect.stringMatching(/day\/?\?plan=7&date=2026-10-12/));
  });

  it("a day with nothing to cook says so", () => {
    render(<TodayView plan={plan()} today="2026-10-13" />);
    expect(screen.getByText("Nothing to cook, eating prepped meals")).toBeInTheDocument();
  });

  it("a plan that starts later or has ended says when", () => {
    const { rerender } = render(<TodayView plan={plan()} today="2026-10-10" />);
    expect(screen.getByText("Your plan starts Monday.")).toBeInTheDocument();
    rerender(<TodayView plan={plan()} today="2026-10-20" />);
    expect(screen.getByText("Your plan ended Tuesday.")).toBeInTheDocument();
    expect(todayInPlan(plan(), "2026-10-12")).toEqual({ kind: "today", index: 0 });
  });
});
