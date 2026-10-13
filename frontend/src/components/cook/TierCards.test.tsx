import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import type { CookAnswers, TierCard, TierFix } from "@/lib/api/types";
import { emptyPrepDraft, type PrepDraft, withDayFix } from "@/lib/cook/prep";
import { mockApi } from "@/test/api";
import { userSettings } from "@/test/fixtures";

import { forgetTierCards, isSlow, keptCards, TierCards } from "./TierCards";

const TODAY = new Date(2026, 9, 12); // Mon Oct 12; cook days Mon, Wed, Thu, Sat, Sun at 90 min
const settings = userSettings();
const ANSWERS: CookAnswers = { schema_version: 1, mode: "prep", prep: { shape: "portions", slot: "lunch", portions: 5, start: "today", cook_style: "mix" }, shopping: "make_a_list", allow_llm: true } as CookAnswers;
const PATH = "/api/v1/cook/meal-prep/tiers";

function card(tier: TierCard["tier"], label: string, extra: Partial<TierCard> = {}): TierCard {
  return { tier, label, blurb: `${label} blurb`, status: "estimated", total_cents: 1000, total_display: "about $10.00", same_as_display: null, protein_per_day_display: "about 40 g protein a day", reason: null, stock_up_cents: 0, stock_up_display: null, includes_display: null, shortfall_display: null, less_than_display: null, fixes: [], cached: false, ...extra } as TierCard;
}

const BROKE = card("broke", "Broke mode", { total_cents: 1973, total_display: "about $19.73" });
const CHEAPEST = card("cheapest", "Cheapest", { total_cents: 1966, total_display: "about $19.66", same_as_display: "Same as Broke mode this week" });
const BETTER = card("better", "A bit better", { total_cents: 2480, total_display: "about $24.80" });
const FANCY = card("fancy", "Fancy", { total_cents: 2510, total_display: "about $25.10", same_as_display: "Same as A bit better this week" });
const FOUR = [BROKE, CHEAPEST, BETTER, FANCY];

function lines(cards: TierCard[], status = "succeeded"): unknown[] {
  return [{ event: "started", run_id: 7, elapsed_s: 0 }, ...cards.map((c) => ({ event: "card", run_id: 7, elapsed_s: 1, card: c })), { event: "result", run_id: 7, elapsed_s: 2, status, cards }];
}

/** A tier stream the test feeds line by line (to see a card arrive before the next). */
function controlledStream() {
  let push: (line: unknown) => void = () => undefined;
  let end: () => void = () => undefined;
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      push = (line) => controller.enqueue(encoder.encode(JSON.stringify(line) + "\n"));
      end = () => controller.close();
    },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status: 200, headers: { "content-type": "application/x-ndjson" } })),
  );
  return { push: (line: unknown) => push(line), end: () => end() };
}

function Cards({ onFix = () => undefined }: { onFix?: (fix: TierFix) => void }) {
  return <TierCards answers={ANSWERS} selected={null} online onPick={() => undefined} onFix={onFix} />;
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetTierCards();
});

describe("the tier cards (AC3–AC6)", () => {
  it("show each card as soon as its estimate is ready, Broke mode first", async () => {
    const stream = controlledStream();
    render(<Cards />);
    expect(screen.getByText("Pricing four ways to shop this week…")).toBeInTheDocument();
    stream.push({ event: "started", run_id: 7, elapsed_s: 0 });
    stream.push({ event: "card", run_id: 7, elapsed_s: 3, card: BROKE });
    expect(await screen.findByRole("button", { name: /Broke mode/ })).toHaveTextContent("about $19.73 groceries");
    expect(screen.queryByRole("button", { name: /Cheapest/ })).not.toBeInTheDocument();
    expect(screen.getByText("Pricing the next one…")).toBeInTheDocument();
    stream.push({ event: "card", run_id: 7, elapsed_s: 6, card: CHEAPEST });
    expect(await screen.findByRole("button", { name: /Cheapest/ })).toBeInTheDocument();
    for (const line of lines(FOUR).slice(3)) stream.push(line);
    stream.end();
    await waitFor(() => expect(screen.queryByText("Pricing the next one…")).not.toBeInTheDocument());
    const order = screen.getAllByRole("listitem").map((li) => ["Broke mode", "Cheapest", "A bit better", "Fancy"].find((label) => li.textContent?.startsWith(label)));
    expect(order).toEqual(["Broke mode", "Cheapest", "A bit better", "Fancy"]);
  });

  it("a card that costs no more than the one below says so instead of a lower price (AC3)", async () => {
    mockApi((c) => (c.path === PATH ? { lines: lines(FOUR) } : undefined));
    render(<Cards />);
    const cheapest = await screen.findByRole("button", { name: /Cheapest/ });
    expect(cheapest).toHaveTextContent("Same as Broke mode this week");
    expect(cheapest).not.toHaveTextContent("$19.66");
    expect(screen.getByRole("button", { name: /Fancy/ })).toHaveTextContent("Same as A bit better this week");
    expect(screen.getByRole("button", { name: /^A bit better/ })).toHaveTextContent("about $24.80 groceries");
  });

  it("a card that costs less than the one below shows its real price and why, never hidden (AD1)", async () => {
    const less = card("better", "A bit better", { total_cents: 727, total_display: "about $7.27", less_than_display: "Costs less than Cheapest this week: about $7.27, uses more of what you have." });
    mockApi((c) => (c.path === PATH ? { lines: lines([BROKE, card("cheapest", "Cheapest", { total_cents: 1931, total_display: "about $19.31" }), less]) } : undefined));
    render(<Cards />);
    const better = await screen.findByRole("button", { name: /^A bit better/ });
    expect(better).toHaveTextContent("about $7.27 groceries");
    expect(better).toHaveTextContent("Costs less than Cheapest this week: about $7.27, uses more of what you have.");
    expect(better).not.toHaveTextContent("Same as");
  });

  it("a card's shortfall says why, and its fix is a button beside it (AC4)", async () => {
    const fix: TierFix = { kind: "mood", label: "Allow fancy recipes on Saturday", day: "2026-10-17", mood: "fancy", minutes: null };
    const fancy = card("fancy", "Fancy", { includes_display: "Up to 3 of one recipe a week", shortfall_display: "No meals with salmon, shrimp or similar this week: the recipes with them are fancy to cook, and none of your cook days allows fancy recipes.", fixes: [fix] });
    mockApi((c) => (c.path === PATH ? { lines: lines([BROKE, CHEAPEST, BETTER, fancy]) } : undefined));
    const onFix = vi.fn();
    render(<Cards onFix={onFix} />);
    expect(await screen.findByRole("button", { name: /Fancy/ })).toHaveTextContent("none of your cook days allows fancy recipes.");
    await userEvent.click(screen.getByRole("button", { name: "Allow fancy recipes on Saturday" }));
    expect(onFix).toHaveBeenCalledWith(fix);
  });

  it("a week that can't be planned says why, with its fix; its card can't be picked (AC5)", async () => {
    const why = "Tue 13's dinner comes before your first cook day (Wed 14), so nothing can be cooked for it.";
    const fix: TierFix = { kind: "minutes", label: "Cook on Tuesday too", day: "2026-10-13", mood: null, minutes: 90 };
    const start: TierFix = { kind: "start", label: "Start tomorrow", day: "2026-10-13", mood: null, minutes: null };
    const none = FOUR.map((c) => ({ ...c, status: "none_fits", total_cents: null, total_display: null, same_as_display: null, reason: why, fixes: [start, fix] }) as TierCard);
    mockApi((c) => (c.path === PATH ? { lines: lines(none) } : undefined));
    render(<Cards />);
    expect(await screen.findByRole("button", { name: /Broke mode/ })).toBeDisabled();
    expect(screen.getAllByText(why)).toHaveLength(4);
    expect(screen.getAllByRole("button", { name: "Cook on Tuesday too" })).toHaveLength(4);
    expect(screen.getAllByRole("button", { name: "Start tomorrow" })).toHaveLength(4); // AD2: both fixes
    expect(screen.queryByText(/No week fits/)).not.toBeInTheDocument();
  });

  it("a card that ran out of time is Taking longer than usual: still pickable, and Try again prices it again (AC5)", async () => {
    let n = 0;
    const slow = card("fancy", "Fancy", { status: "timed_out", total_cents: null, total_display: null, protein_per_day_display: null, reason: "Taking longer than usual." });
    const calls = mockApi((c) => (c.path === PATH ? { lines: (n += 1) === 1 ? lines([BROKE, CHEAPEST, BETTER, slow], "partial") : lines(FOUR) } : undefined));
    render(<Cards />);
    const fancy = await screen.findByRole("button", { name: /Fancy/ });
    expect(fancy).toBeEnabled();
    expect(fancy).toHaveTextContent("Taking longer than usual.");
    expect(fancy).not.toHaveTextContent("No week fits");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Fancy/ })).toHaveTextContent("Same as A bit better this week"));
    expect(calls).toHaveLength(2);
  });

  it.each([
    ["the connection fails (offline, a cold start that never answered)", () => vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))))],
    ["the database is waking up (a 503 before the stream)", () => mockApi(() => ({ status: 503, body: { title: "Taking longer than usual", detail: "The database didn't answer in time; try again in a moment.", code: "db_unavailable" } }))],
    ["the stream ends with the database gone", () => mockApi(() => ({ lines: [{ event: "started", run_id: 7, elapsed_s: 0 }, { event: "result", run_id: 7, elapsed_s: 9, status: "failed", problem: { type: "about:blank", title: "Taking longer than usual", status: 503, detail: "The database didn't answer in time; try again in a moment.", code: "db_unavailable" } }] }))],
    ["the stream stops before its result (Vercel cut it off)", () => mockApi(() => ({ lines: [{ event: "started", run_id: 7, elapsed_s: 0 }, { event: "card", run_id: 7, elapsed_s: 4, card: BROKE }] }))],
  ])("Taking longer than usual with Try again, never No week fits, when %s", async (_why, setUp) => {
    setUp();
    render(<Cards />);
    expect(await screen.findByText("Taking longer than usual")).toBeInTheDocument();
    expect(screen.queryByText(/No week fits/)).not.toBeInTheDocument();
    vi.unstubAllGlobals();
    mockApi((c) => (c.path === PATH ? { lines: lines(FOUR) } : undefined));
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: /Fancy/ })).toBeInTheDocument();
    expect(screen.queryByText("Taking longer than usual")).not.toBeInTheDocument();
  });

  it("reopening the step for the same answers shows the cards at once, with no new request (AC6)", async () => {
    const calls = mockApi((c) => (c.path === PATH ? { lines: lines(FOUR) } : undefined));
    const { unmount } = render(<Cards />);
    await screen.findByRole("button", { name: /Fancy/ });
    unmount();
    render(<Cards />);
    expect(screen.getByRole("button", { name: /Fancy/ })).toBeInTheDocument(); // no "Pricing…" first
    expect(screen.queryByText(/Pricing/)).not.toBeInTheDocument();
    expect(calls).toHaveLength(1);
    expect(keptCards(JSON.stringify({ ...ANSWERS, shopping: "make_a_list", budget_cents: null, price_tier: null }), Date.now() + 11 * 60 * 1000)).toBeNull(); // kept 10 minutes
  });

  it("a set of cards with one out of time isn't kept: reopening prices them again", async () => {
    const slow = card("fancy", "Fancy", { status: "timed_out", total_cents: null, total_display: null, reason: "Taking longer than usual." });
    const calls = mockApi((c) => (c.path === PATH ? { lines: lines([BROKE, slow], "partial") } : undefined));
    const { unmount } = render(<Cards />);
    await screen.findByRole("button", { name: /Fancy/ });
    unmount();
    render(<Cards />);
    await waitFor(() => expect(calls).toHaveLength(2));
  });

  it("knows a slow server from a real error", () => {
    expect(isSlow(new TypeError("Failed to fetch"))).toBe(true);
    expect(isSlow(new ApiError(504, "Gateway Timeout", ""))).toBe(true);
    expect(isSlow(new ApiError(500, "Internal", "", [], null, [], { code: "db_unavailable" }))).toBe(true);
    expect(isSlow(new ApiError(422, "These answers can't make a plan", "Pick a meal"))).toBe(false);
  });
});

describe("a tier card's fix on the draft (AC4, AC5)", () => {
  const base: PrepDraft = { ...emptyPrepDraft(), preset: "five_lunches", style: "mix" }; // Mon 12 – Fri 16
  const mood: TierFix = { kind: "mood", label: "Allow fancy recipes on Wednesday", day: "2026-10-14", mood: "fancy", minutes: null };

  it("Mix it up becomes your cook days as sessions, with that day's own mood", () => {
    expect(withDayFix(base, mood, settings, TODAY)).toMatchObject({
      style: "sessions",
      sessions: [
        { day: "2026-10-12", minutes: 90 },
        { day: "2026-10-14", minutes: 90, mood: "fancy" },
        { day: "2026-10-15", minutes: 90 },
      ],
    });
  });

  it("Cook on Tuesday too: a day that isn't a cook day becomes one, with the minutes", () => {
    const fix: TierFix = { kind: "minutes", label: "Cook on Tuesday too", day: "2026-10-13", mood: null, minutes: 90 };
    expect(withDayFix(base, fix, settings, TODAY).sessions).toEqual([
      { day: "2026-10-12", minutes: 90 },
      { day: "2026-10-13", minutes: 90 },
      { day: "2026-10-14", minutes: 90 },
      { day: "2026-10-15", minutes: 90 },
    ]);
  });

  it("raises a session's minutes, never lowers them", () => {
    const sessions: PrepDraft = { ...base, style: "sessions", sessions: [{ day: "2026-10-14", minutes: 120 }] };
    const raise: TierFix = { kind: "minutes", label: "Allow 55 min on Wednesday", day: "2026-10-14", mood: null, minutes: 55 };
    expect(withDayFix(sessions, raise, settings, TODAY).sessions).toEqual([{ day: "2026-10-14", minutes: 120 }]);
  });

  it("Start tomorrow moves the plan's first day; a big cook day before it moves with it (AD2)", () => {
    const start: TierFix = { kind: "start", label: "Start tomorrow", day: "2026-10-13", mood: null, minutes: null };
    expect(withDayFix(base, start, settings, TODAY)).toMatchObject({ start: "tomorrow", style: "mix" });
    const big: PrepDraft = { ...base, style: "big_day", cookDay: "today" };
    expect(withDayFix(big, start, settings, TODAY)).toMatchObject({ start: "tomorrow", cookDay: null }); // the start day
  });

  it("one big cook day takes it on its own day", () => {
    const big: PrepDraft = { ...base, style: "big_day", cookDay: "2026-10-14", cookMinutes: 60 };
    expect(withDayFix(big, mood, settings, TODAY)).toMatchObject({ style: "big_day", mood: "fancy", cookMinutes: 60 });
    const minutes: TierFix = { kind: "minutes", label: "Allow 95 min on Wednesday", day: "2026-10-14", mood: null, minutes: 95 };
    expect(withDayFix(big, minutes, settings, TODAY)).toMatchObject({ style: "big_day", cookMinutes: 95 });
  });
});
