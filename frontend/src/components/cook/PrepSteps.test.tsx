import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { buildPrepAnswers, emptyPrepDraft, type PrepDraft, prepDraftFromAnswers } from "@/lib/cook/prep";
import { reducePrep, initialPrepState, prepStages } from "@/lib/cook/prepRun";
import type { PlanStreamEvent } from "@/lib/api/types";
import { mockApi } from "@/test/api";
import { userSettings } from "@/test/fixtures";

import { AmountStep, CookStyleStep, FREEZER_EXTRA_NOTE, ShopStep } from "./PrepSteps";

const TODAY = new Date(2026, 9, 12); // Mon Oct 12; cook days Mon, Wed, Thu, Sat, Sun at 90 min (the seed default)
const settings = userSettings();

let latest: PrepDraft = emptyPrepDraft();

function Harness({ step, initial, onNext = () => undefined }: { step: "amount" | "when" | "shop"; initial: Partial<PrepDraft>; onNext?: () => void }) {
  const [draft, setDraft] = useState<PrepDraft>({ ...emptyPrepDraft(), ...initial });
  latest = draft;
  const props = { draft, settings, onChange: setDraft, onBack: () => undefined, onNext, today: TODAY };
  if (step === "amount") return <AmountStep {...props} />;
  if (step === "when") return <CookStyleStep {...props} />;
  return <ShopStep {...props} online />;
}

async function typeMinutes(label: string, value: string) {
  await userEvent.click(screen.getByRole("button", { name: new RegExp(`^${label}: .*Tap to type a number`) }));
  const input = screen.getByRole("textbox", { name: `${label}, type a number` });
  await userEvent.clear(input);
  await userEvent.type(input, `${value}{Enter}`);
}

describe("C1b How do you want to cook? (H5): the four options, down to the request", () => {
  it("One big cook day: the day and its start-to-finish minutes, well above the usual; a whole week on one day", async () => {
    render(<Harness step="when" initial={{ preset: "usual_week" }} />);
    await userEvent.click(screen.getByRole("button", { name: /One big cook day/ }));
    // pre-filled from that day's schedule: Monday's 90 minutes
    expect(screen.getByRole("button", { name: /^Time in the kitchen: 1 h 30 min/ })).toBeInTheDocument();
    await typeMinutes("Time in the kitchen", "420");
    const answers = buildPrepAnswers(latest, settings, TODAY);
    expect(answers.prep).toMatchObject({ shape: "days", day_count: 7, slots: ["breakfast", "lunch", "dinner", "protein_dessert"], cook_style: "big_day", cook_day: "today", cook_minutes: 420, sessions: [] });
    // another day of the plan: its own minutes (Tuesday isn't a cook day, so the longest cook day's)
    await userEvent.click(within(screen.getByRole("group", { name: "Cook on" })).getByRole("button", { name: "Tomorrow" }));
    expect(buildPrepAnswers(latest, settings, TODAY).prep).toMatchObject({ cook_day: "tomorrow", cook_minutes: null });
  });

  it("A few sessions: the plan's cook days from your settings, each with its minutes", async () => {
    render(<Harness step="when" initial={{ preset: "lunch_dinner_5" }} />);
    await userEvent.click(screen.getByRole("button", { name: /A few sessions/ }));
    const chips = within(screen.getByRole("group", { name: "Cook days" }));
    // Mon 12 – Fri 16: Mon, Wed and Thu are cook days
    expect(chips.getAllByRole("button", { pressed: true }).map((b) => b.textContent)).toEqual(["✓ Today", "✓ Wed 14", "✓ Thu 15"]);
    await userEvent.click(chips.getByRole("button", { name: /Thu 15/ }));
    await typeMinutes("Wed 14", "150");
    expect(buildPrepAnswers(latest, settings, TODAY).prep).toMatchObject({
      cook_style: "sessions",
      sessions: [
        { day: "2026-10-12", minutes: 90 },
        { day: "2026-10-14", minutes: 150 },
      ],
    });
  });

  it("Same dish, many portions: one dish for 8 portions, cooked on the day you pick", async () => {
    render(<Harness step="when" initial={{ preset: "custom", shape: "portions", slot: "dinner", portions: 8 }} />);
    await userEvent.click(screen.getByRole("button", { name: /Same dish, many portions/ }));
    expect(screen.getByText("One recipe for all 8 portions.")).toBeInTheDocument();
    const answers = buildPrepAnswers(latest, settings, TODAY);
    expect(answers.prep).toMatchObject({ shape: "portions", slot: "dinner", portions: 8, cook_style: "same_dish", cook_day: "today" });
  });

  it("Mix it up: your cook days and the variety rule, no controls", async () => {
    render(<Harness step="when" initial={{ preset: "five_lunches" }} />);
    await userEvent.click(screen.getByRole("button", { name: /Mix it up/ }));
    expect(buildPrepAnswers(latest, settings, TODAY).prep).toMatchObject({ shape: "portions", slot: "lunch", portions: 5, cook_style: "mix", cook_minutes: null, sessions: [] });
  });

  it("the fifth tile, Cook basics, mix and match, shows coming soon (2b.11)", () => {
    render(<Harness step="when" initial={{ preset: "five_lunches" }} />);
    const basics = screen.getByRole("button", { name: /Cook basics, mix and match/ });
    expect(basics).toBeDisabled();
    expect(basics).toHaveTextContent("coming soon");
  });

  it("Next waits for a choice, and a cook day needs some time", async () => {
    const onNext = vi.fn();
    render(<Harness step="when" initial={{ preset: "five_lunches" }} onNext={onNext} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByText("Pick how you want to cook")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /One big cook day/ }));
    await typeMinutes("Time in the kitchen", "0");
    expect(screen.getByText("Give your cook day some time")).toBeInTheDocument();
  });
});

describe("C1 How much are you prepping?", () => {
  it("presets, or Something else by portions or by days, starting today, tomorrow or a date", async () => {
    render(<Harness step="amount" initial={{}} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Something else/ }));
    await userEvent.click(screen.getByRole("button", { name: "By days" }));
    await userEvent.click(within(screen.getByRole("group", { name: "Meals" })).getByRole("button", { name: /Breakfast/ }));
    await userEvent.click(within(screen.getByRole("group", { name: "Starting" })).getByRole("button", { name: "Tomorrow" }));
    fireEvent.click(screen.getByRole("button", { name: "More cook extra for the freezer (future weeks)" }));
    const answers = buildPrepAnswers({ ...latest, style: "mix" }, settings, TODAY);
    expect(answers.prep).toMatchObject({ shape: "days", day_count: 5, slots: ["breakfast"], start: "tomorrow", extra_to_freeze: 1 });
  });

  it("freezer extras (AA2): named for future weeks, explained as outside this plan, and 0 unless you add some", () => {
    render(<Harness step="amount" initial={{ preset: "five_lunches" }} />);
    expect(screen.getByText("Cook extra for the freezer (future weeks)")).toBeInTheDocument();
    expect(screen.getByText(FREEZER_EXTRA_NOTE)).toBeInTheDocument();
    expect(emptyPrepDraft().extraToFreeze).toBe(0);
    expect(buildPrepAnswers({ ...latest, style: "mix" }, settings, TODAY).prep?.extra_to_freeze).toBe(0);
  });

  it("a meal with no calories set says so, with a link to set them", async () => {
    render(<Harness step="amount" initial={{ preset: "custom", shape: "portions" }} />);
    await userEvent.click(within(screen.getByRole("group", { name: "Meal" })).getByRole("button", { name: /Snack/ }));
    expect(screen.getByText("Snack has no calories set")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("link", { name: /Set the calories for snack/ })).toHaveAttribute("href", expect.stringMatching(/field=meals/));
  });
});

const CARDS = [
  { tier: "cheapest", label: "Cheapest", blurb: "Cheap staples: chicken thighs, eggs, lentils, rice, frozen veg, tortillas", status: "estimated", total_cents: 3905, total_display: "about $39.05", protein_per_day_display: "about 130 g protein a day", reason: null },
  { tier: "better", label: "A bit better", blurb: "Adds chicken breast, Greek yogurt, ground turkey and more fresh veg", status: "estimated", total_cents: 4512, total_display: "about $45.12", protein_per_day_display: "about 129 g protein a day", reason: null },
  { tier: "fancy", label: "Fancy", blurb: "Adds salmon, shrimp and other premium picks, with more variety", status: "none_fits", total_cents: null, total_display: null, protein_per_day_display: null, reason: "No week fits your limits with the Fancy tier's groceries." },
];

describe("C3b Shopping for this? (AA6: budget tiers)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("three tier cards for this week, each with its estimate; a tap picks the tier", async () => {
    const calls = mockApi((c) => (c.path === "/api/v1/cook/meal-prep/tiers" ? { body: CARDS } : undefined));
    render(<Harness step="shop" initial={{ preset: "five_lunches", style: "mix" }} />);
    expect(screen.getByRole("button", { name: "Build my plan" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Make me a shopping list/ }));
    const cheapest = await screen.findByRole("button", { name: /Cheapest/ });
    expect(cheapest).toHaveTextContent("about $39.05");
    expect(cheapest).toHaveTextContent("about 130 g protein a day");
    expect(screen.getByRole("button", { name: /Fancy/ })).toBeDisabled();
    expect(screen.getByText("No week fits your limits with the Fancy tier's groceries.")).toBeInTheDocument();
    expect(screen.getByText("Pick a tier or set your own limit")).toBeInTheDocument();
    await userEvent.click(cheapest);
    expect(cheapest).toHaveAttribute("aria-pressed", "true");
    expect(buildPrepAnswers(latest, settings, TODAY)).toMatchObject({ shopping: "make_a_list", price_tier: "cheapest", budget_cents: null });
    expect(screen.getByRole("button", { name: "Build my plan" })).toBeEnabled();
    expect(calls[0]?.body).toMatchObject({ mode: "prep", shopping: "make_a_list", price_tier: null, budget_cents: null });
  });

  it("Set my own limit takes a budget number instead; Use what I have none", async () => {
    mockApi((c) => (c.path === "/api/v1/cook/meal-prep/tiers" ? { body: CARDS } : undefined));
    render(<Harness step="shop" initial={{ preset: "five_lunches", style: "mix" }} />);
    await userEvent.click(screen.getByRole("button", { name: /Make me a shopping list/ }));
    await userEvent.click(screen.getByRole("button", { name: "Set my own limit" }));
    fireEvent.change(screen.getByRole("slider"), { target: { value: "4500" } });
    expect(buildPrepAnswers(latest, settings, TODAY)).toMatchObject({ shopping: "make_a_list", budget_cents: 4500, price_tier: null });
    expect(screen.getByText(/listed separately/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Use what I have/ }));
    expect(buildPrepAnswers(latest, settings, TODAY)).toMatchObject({ shopping: "use_what_i_have", budget_cents: null, price_tier: null });
  });
});

describe("the meal-prep draft", () => {
  it("comes back from your last answers, without last time's extras, and a past date becomes today", () => {
    const draft: PrepDraft = { ...emptyPrepDraft(), preset: "lunch_dinner_5", style: "sessions", sessions: [{ day: "2026-10-14", minutes: 120 }], goals: ["protein", "quick"], quickMinutes: 45, mood: "simple", shopping: "make_a_list", budgetCents: 5000, extras: [{ ingredient_id: 7, name: "chickpeas", status: "could_buy" }] };
    const back = prepDraftFromAnswers(buildPrepAnswers(draft, settings, TODAY), TODAY);
    expect(back).toMatchObject({ preset: "lunch_dinner_5", style: "sessions", sessions: [{ day: "2026-10-14", minutes: 120 }], goals: ["protein", "quick"], quickMinutes: 45, mood: "simple", budgetCents: 5000, extras: [] });
    const old = buildPrepAnswers({ ...draft, start: "2026-10-01", sessions: [{ day: "2026-10-02", minutes: 90 }] }, settings, TODAY);
    expect(prepDraftFromAnswers(old, TODAY)).toMatchObject({ start: "today", sessions: [] });
  });
});

describe("sessions outside the plan", () => {
  it("are left out when you shorten the plan after picking them (the server would refuse them)", () => {
    const draft: PrepDraft = { ...emptyPrepDraft(), preset: "custom", shape: "days", dayCount: 3, slots: ["lunch"], style: "sessions", sessions: [{ day: "2026-10-12", minutes: 90 }, { day: "2026-10-17", minutes: 90 }] };
    expect(buildPrepAnswers(draft, settings, TODAY).prep?.sessions).toEqual([{ day: "2026-10-12", minutes: 90 }]);
  });
});

describe("C4 Building for meal prep: the real stages", () => {
  it("moves only when the server reports a stage, shows the countdown, and the rounding re-solve", () => {
    const at = (state: ReturnType<typeof initialPrepState>) => prepStages(state).map((s) => `${s.label}:${s.state}`);
    let state = initialPrepState();
    const line = (stage: string, extra: Partial<PlanStreamEvent> = {}): PlanStreamEvent => ({ event: "progress", run_id: 4, elapsed_s: 1, stage, message: `m-${stage}`, ...extra }) as PlanStreamEvent;
    state = reducePrep(state, line("generating", { message: "Finding recipes: writing new ones for lunch" }));
    expect(at(state)).toEqual(["Checking your pantry:done", "Finding recipes:current", "Balancing calories across the days:pending", "Pricing your groceries:pending", "Double-checking every number:pending"]);
    expect(prepStages(state)[1]?.note).toBe("Finding recipes: writing new ones for lunch");
    state = reducePrep(state, line("waiting", { wait_s: 23 }), 1000);
    expect(state.wait).toEqual({ seconds: 23, startedAt: 1000 });
    state = reducePrep(state, line("re-solving"));
    expect(prepStages(state)[2]).toMatchObject({ state: "current", note: "Adjusting after rounding" });
    state = reducePrep(state, { event: "result", run_id: 4, elapsed_s: 30, status: "succeeded", plan_id: 9 } as PlanStreamEvent);
    expect(state).toMatchObject({ status: "succeeded", planId: 9, wait: null });
    expect(prepStages(state).every((s) => s.state === "done")).toBe(true);
  });
});
