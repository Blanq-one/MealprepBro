import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { orderDays, readPlanTab, VIEW_KEY } from "@/lib/plan/days";
import { mockApi } from "@/test/api";
import { batch, day, groceryByStore, meal, plan } from "@/test/fixtures";

import { dayHeading, PlanView } from "./PlanView";

const MON = "2026-10-12";
const TUE = "2026-10-13";
const WED = "2026-10-14";
const SAT = "2026-10-17";

/** A meal-prep plan Mon–Wed, cooking Monday: Monday's batch feeds four meals, one from the freezer on Saturday. */
function prepPlan(overrides: Parameters<typeof plan>[0] = {}) {
  return plan({
    kind: "meal_prep",
    header: "Lunch + Dinner, 3 days · Mon 12 – Wed 14 · High protein",
    batches: [batch()],
    days: [
      day({
        day: MON,
        time_display: "about 55 min start to finish · 35 min hands-on",
        freeze_steps: ["Freeze 1 pack of chicken thighs today (shopping day): you'll use it Wed."],
        freeze_today: ["Freeze 1 portion of Chicken over rice once cooled."],
        timeline: [
          { at_min: 0, at_display: "0:00", text: "Preheat the oven to 425°F", kind: "preheat", minutes: 10, equipment: "oven", estimated: false, dish: null, cook_batch_id: null },
          { at_min: 0, at_display: "0:00", text: "Chop the chicken (12 min)", kind: "hands_on", minutes: 12, equipment: null, estimated: false, dish: "Chicken over rice", cook_batch_id: 11 },
          { at_min: 55, at_display: "0:55", text: "Done", kind: "done", minutes: 0, equipment: null, estimated: false, dish: null, cook_batch_id: null },
        ],
        meals: [meal({ eat_on: MON, slot: "lunch", source_display: "Cooked today" })],
      }),
      day({
        day: TUE,
        is_cook_day: false,
        hands_on_minutes: 0,
        cook_note: "Nothing to cook, eating prepped meals",
        thaw_notes: ["Thaw tomorrow's lunch (Chicken over rice) in the fridge tonight."],
        meals: [
          meal({ eat_on: TUE, slot: "dinner", storage: "fridge", source_display: "From the fridge, cooked Mon 12" }),
          meal({
            eat_on: TUE,
            slot: "lunch",
            kind: "assembly",
            cook_batch_id: null,
            recipe_version_id: 90,
            title: "Chicken curry with rice",
            dish_category: "curry",
            source_display: "From the fridge, cooked Mon 12",
            storage: "fridge",
            components: [
              { cook_batch_id: 21, recipe_version_id: 70, title: "Chicken curry", label: "chicken curry", portions: "1.0", portions_display: "1 portion", storage: "fridge", source_display: "From the fridge, cooked Mon 12" },
              { cook_batch_id: 22, recipe_version_id: 71, title: "Plain rice", label: "rice", portions: "0.5", portions_display: "½ portion", storage: "fridge", source_display: "From the fridge, cooked Mon 12" },
            ],
            instruction: "Reheat 1 portion chicken curry and ½ portion rice to 165°F.",
          }),
        ],
      }),
      day({
        day: WED,
        is_cook_day: false,
        hands_on_minutes: 0,
        cook_note: "Nothing to cook, eating prepped meals",
        finish_tasks: [{ id: 5, cook_batch_id: 23, kind: "stage", text: "Roast the marinated tandoori drumsticks (1 portion): 425°F for 40 min, until it reaches 165°F.", time_display: "40 min, 5 hands-on", hands_on_minutes: 5, hands_off_minutes: 35, equipment: "oven", status: "planned" }],
        meals: [meal({ eat_on: WED, slot: "lunch", storage: "freezer", from_freezer: true, source_display: "From the freezer, cooked Mon 12 · thaw Tue 13 night" })],
      }),
    ],
    prep_notes: {
      display: "2 to freeze · 1 may spoil · About this plan",
      items: [
        { kind: "freeze", text: "Freeze 1 pack of chicken thighs today (shopping day): you'll use it Wed.", day: MON },
        { kind: "freeze_portions", text: "Freeze 1 portion of Chicken over rice after cooking on Mon 12.", day: MON },
        { kind: "spoil", text: "spinach: about 120 g left with no use planned, so it may spoil.", day: null },
        { kind: "about", text: "Left out Spicy beef chili: uses beef", day: null },
      ],
    },
    ...overrides,
  });
}

function view(today = MON, overrides: Parameters<typeof plan>[0] = {}) {
  const onAccepted = vi.fn();
  render(<PlanView plan={prepPlan(overrides)} online today={today} onAccepted={onAccepted} />);
  return { onAccepted };
}

beforeEach(() => {
  try {
    window.localStorage.removeItem(VIEW_KEY);
  } catch {
    // no storage
  }
});
afterEach(() => vi.unstubAllGlobals());

describe("C6: the plan view (step 2b.7)", () => {
  it("starts with Today, then the following days; earlier days fold into Earlier in this plan", () => {
    const days = prepPlan().days;
    expect(orderDays(days, TUE).upcoming.map((d) => d.day)).toEqual([TUE, WED]);
    expect(orderDays(days, TUE).earlier.map((d) => d.day)).toEqual([MON]);
    view(TUE);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.slice(0, 2)).toEqual(["Today · Tue 13", "Tomorrow · Wed 14"]);
    const earlier = screen.getByText("Earlier in this plan").closest("details");
    expect(earlier).not.toHaveAttribute("open");
    expect(within(earlier as HTMLElement).getByRole("heading", { name: "Mon Oct 12" })).toBeInTheDocument();
    expect(dayHeading(SAT, MON)).toBe("Sat Oct 17");
  });

  it("each cook day lists its batches and where every portion goes (cook once, eat many, F23)", () => {
    view();
    const cook = screen.getByLabelText("Cook today");
    expect(within(cook).getByText("Cook Chicken over rice ×4")).toBeInTheDocument();
    expect(within(cook).getByText("→ Mon lunch, Tue dinner, Wed lunch, Sat dinner (1 to the freezer)")).toBeInTheDocument();
    expect(within(cook).getByText(/4 portions \(3 fridge, 1 freezer\) · Freezes well/)).toBeInTheDocument();
    expect(within(cook).getByRole("link", { name: /Cook Chicken over rice/ })).toHaveAttribute("href", expect.stringMatching(/^\/recipe\/?\?batch=11$/));
    expect(within(cook).getByText("Freeze 1 portion of Chicken over rice once cooled.")).toBeInTheDocument();
  });

  it("each meal row says where its portion comes from, and the day before a freezer meal says to thaw it", () => {
    view();
    const tuesday = screen.getByRole("region", { name: "Tomorrow · Tue 13" });
    const dinner = within(tuesday).getAllByRole("link").find((l) => l.textContent?.includes("Dinner"));
    expect(dinner).toHaveTextContent("From the fridge, cooked Mon 12");
    expect(screen.getByText("From the freezer, cooked Mon 12 · thaw Tue 13 night")).toBeInTheDocument();
    expect(screen.getByText("Thaw tomorrow's lunch (Chicken over rice) in the fridge tonight.")).toBeInTheDocument();
  });

  it("a shopping day shows its freeze steps on the day itself, as well as in Prep notes", () => {
    view();
    const monday = screen.getByRole("region", { name: "Today · Mon 12" });
    expect(within(monday).getByText("Freeze 1 pack of chicken thighs today (shopping day): you'll use it Wed.")).toBeInTheDocument();
  });

  it("an assembled meal shows its items, their portions and the eating-day instruction, and opens its page", () => {
    view();
    const link = screen.getByRole("link", { name: /Chicken curry with rice/ });
    expect(link).toHaveAttribute("href", expect.stringMatching(/^\/recipe\/?\?version=90$/));
    expect(within(link).getByText("1 portion chicken curry · ½ portion rice")).toBeInTheDocument();
    expect(within(link).getByText("Reheat 1 portion chicken curry and ½ portion rice to 165°F.")).toBeInTheDocument();
  });

  it("a day with nothing to cook says so; an eating day lists its finish tasks first", () => {
    view();
    const tuesday = screen.getByRole("region", { name: "Tomorrow · Tue 13" });
    expect(within(tuesday).getByText("Nothing to cook, eating prepped meals")).toBeInTheDocument();
    const wednesday = screen.getByRole("region", { name: "Wed Oct 14" });
    const tasks = within(wednesday).getByRole("list", { name: "Finish today" });
    expect(tasks).toHaveTextContent("Roast the marinated tandoori drumsticks (1 portion): 425°F for 40 min, until it reaches 165°F.");
    expect(tasks).toHaveTextContent("40 min, 5 hands-on");
    // finish tasks come before the meals
    const meals = within(wednesday).getByRole("list", { name: "Meals" });
    expect(tasks.compareDocumentPosition(meals) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("freeze, spoil and left-out notes sit behind one Prep notes row, never above the days", async () => {
    view();
    const row = screen.getByRole("button", { name: /Prep notes/ });
    expect(row).toHaveTextContent("Prep notes: 2 to freeze · 1 may spoil · About this plan");
    // nothing about freezing, spoiling or left-out recipes sits between the header and the days
    expect(screen.queryByText("Left out Spicy beef chili: uses beef")).toBeNull();
    expect(screen.queryByText(/may spoil\.$/)).toBeNull();
    await userEvent.click(row);
    const sheet = screen.getByRole("dialog", { name: "Prep notes" });
    expect(within(sheet).getByRole("region", { name: "To freeze" })).toHaveTextContent("Freeze 1 portion of Chicken over rice after cooking on Mon 12.");
    expect(within(sheet).getByRole("region", { name: "May spoil" })).toHaveTextContent("spinach");
    expect(within(sheet).getByRole("region", { name: "About this plan" })).toHaveTextContent("Left out Spicy beef chili: uses beef");
  });

  it("no notes, no row", () => {
    view(MON, { prep_notes: null });
    expect(screen.queryByRole("button", { name: /Prep notes/ })).toBeNull();
  });

  it("a cook day shows its timeline (in place of the prep order) and starts the cook-day cooking mode", async () => {
    view();
    const summary = screen.getByText(/^Timeline/);
    expect(summary).toHaveTextContent("Timeline · about 55 min start to finish · 35 min hands-on");
    await userEvent.click(summary);
    expect(screen.getByText("Chop the chicken (12 min)")).toBeVisible();
    expect(screen.getByRole("link", { name: "Start cooking" })).toHaveAttribute("href", expect.stringMatching(/^\/cook\/cooking\/?\?plan=7&day=2026-10-12$/));
  });

  it("the header carries the API's header and totals: groceries and stock-up apart, today's hands-on time", () => {
    view(MON, { costs: { ...plan().costs, cash_split_display: "$24.10 groceries + $62.50 stock-up" } });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Lunch + Dinner, 3 days · Mon 12 – Wed 14 · High protein");
    expect(screen.getByText("$24.10 groceries + $62.50 stock-up · 35 min hands-on today")).toBeInTheDocument();
  });

  it("Recipes | Shopping list: the list is read-only here, opens in Grocery, and the choice is remembered", async () => {
    mockApi((call) => (call.path.startsWith("/api/v1/plans/7/grocery-list") ? { body: groceryByStore } : undefined));
    view();
    await userEvent.click(screen.getByRole("button", { name: "Shopping list" }));
    expect(await screen.findByText("Stop & Shop")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Got chicken thigh/ })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Open in Grocery" })).toHaveAttribute("href", expect.stringMatching(/^\/grocery\/?\?plan=7$/));
    expect(readPlanTab()).toBe("shopping");
  });
});

describe("Use this plan (E6)", () => {
  it("accepts a draft; when it overlaps your current plan, a sheet asks first and Replace it replaces", async () => {
    const accepted = { ...prepPlan(), status: "active" };
    const calls = mockApi((call) => {
      if (call.path === "/api/v1/plans/7/accept") {
        return {
          status: 409,
          body: { title: "This plan overlaps your current plan", detail: "Replace your current plan (Mon 12 – Sun 18, 21 meals)?", code: "plan_overlap", overlapping: [{ plan_id: 4, start: MON, end: "2026-10-18", meals: 21, message: "Replace your current plan (Mon 12 – Sun 18, 21 meals)?" }] },
        };
      }
      if (call.path === "/api/v1/plans/7/accept?replace_overlapping=true") return { body: accepted };
      return undefined;
    });
    const { onAccepted } = view();
    await userEvent.click(screen.getByRole("button", { name: "Use this plan" }));
    const sheet = await screen.findByRole("dialog", { name: "Replace your current plan?" });
    expect(within(sheet).getByText("Replace your current plan (Mon 12 – Sun 18, 21 meals)?")).toBeInTheDocument();
    expect(onAccepted).not.toHaveBeenCalled();
    await userEvent.click(within(sheet).getByRole("button", { name: "Replace it" }));
    expect(calls.map((c) => c.path)).toEqual(["/api/v1/plans/7/accept", "/api/v1/plans/7/accept?replace_overlapping=true"]);
    expect(onAccepted).toHaveBeenCalledWith(accepted);
  });

  it("Keep my current plan leaves it; the active plan says so instead of the button", async () => {
    mockApi(() => ({ status: 409, body: { title: "Overlap", detail: "x", overlapping: [{ plan_id: 4, start: MON, end: SAT, meals: 12, message: "Replace your current plan (Mon 12 – Sat 17, 12 meals)?" }] } }));
    view();
    await userEvent.click(screen.getByRole("button", { name: "Use this plan" }));
    await userEvent.click(await screen.findByRole("button", { name: "Keep my current plan" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    render(<PlanView plan={{ ...prepPlan(), status: "active" }} online today={MON} onAccepted={() => undefined} />);
    expect(screen.getByText("This is your current plan ✓")).toBeInTheDocument();
  });

  it("offline, Use this plan needs a connection", () => {
    render(<PlanView plan={prepPlan()} online={false} today={MON} onAccepted={() => undefined} />);
    expect(screen.getByRole("button", { name: "Use this plan" })).toBeDisabled();
    expect(screen.getByText("Needs a connection")).toBeInTheDocument();
  });
});
