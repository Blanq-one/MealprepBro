import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { batch, day, plan } from "@/test/fixtures";

import { CookDayMode } from "./CookDayMode";

const MON = "2026-10-12";

function cookDay() {
  const monday = day({
    day: MON,
    time_display: "about 55 min start to finish · 35 min hands-on",
    timeline: [
      { at_min: 0, at_display: "0:00", text: "Preheat the oven to 425°F", kind: "preheat", minutes: 10, equipment: "oven", estimated: false, dish: null, cook_batch_id: null },
      { at_min: 0, at_display: "0:00", text: "Chop the chicken (12 min)", kind: "hands_on", minutes: 12, equipment: null, estimated: false, dish: "Chicken over rice", cook_batch_id: 11 },
      { at_min: 12, at_display: "0:12", text: "Rice on the stove (25 min)", kind: "runs", minutes: 25, equipment: "stovetop", estimated: false, dish: "Dal", cook_batch_id: 12 },
      { at_min: 55, at_display: "0:55", text: "Done", kind: "done", minutes: 0, equipment: null, estimated: false, dish: null, cook_batch_id: null },
    ],
  });
  const p = plan({ batches: [batch(), batch({ id: 12, title: "Dal", uses_display: "Tue lunch" })], days: [monday] });
  return { p, monday };
}

describe("the cook-day cooking mode (FLOW_SPEC §20.4)", () => {
  it("steps through the day's timeline across dishes, each line opening its dish's steps, then Mark cooked per batch", async () => {
    const { p, monday } = cookDay();
    render(<CookDayMode plan={p} day={monday} online />);
    const first = screen.getByRole("region", { name: "Today's batches" });
    expect(first).toHaveTextContent("Chicken over rice ×4");
    expect(first).toHaveTextContent("→ Mon lunch, Tue dinner, Wed lunch, Sat dinner (1 to the freezer)");
    expect(first).toHaveTextContent("Dal ×4");
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(screen.getByText("Preheat the oven to 425°F")).toBeInTheDocument();
    expect(screen.getByText("0:00 · 1 of 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Chop the chicken (12 min)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the Chicken over rice steps" })).toHaveAttribute("href", expect.stringMatching(/^\/recipe\/?\?batch=11$/));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("link", { name: "Open the Dal steps" })).toHaveAttribute("href", expect.stringMatching(/^\/recipe\/?\?batch=12$/));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    const done = screen.getByRole("region", { name: "Done" });
    expect(within(done).getAllByRole("button", { name: "Mark cooked" })).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
  });

  it("leaving goes back to the plan at that day", () => {
    const { p, monday } = cookDay();
    render(<CookDayMode plan={p} day={monday} online />);
    expect(screen.getByRole("link", { name: "Leave cooking mode" })).toHaveAttribute("href", expect.stringMatching(/^\/cook\/plan\/?\?id=7&date=2026-10-12$/));
  });
});
