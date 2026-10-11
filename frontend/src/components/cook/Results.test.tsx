import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import type { CookAnswers } from "@/lib/api/types";
import { mockApi } from "@/test/api";
import { suggestion } from "@/test/fixtures";

import { emptyFixes, type ResultsData, ResultsView } from "./Results";

const answers = { schema_version: 1, mode: "now", goals: ["quick"], time_limit_minutes: 20, mood: "fancy", pantry: [], extras: [], allow_llm: true } as unknown as CookAnswers;

function data(overrides: Partial<ResultsData> = {}): ResultsData {
  return {
    searchId: 5,
    runId: 9,
    header: "Dinner for 1 · Quick · Fancy",
    suggestions: [suggestion()],
    status: "succeeded",
    stage: "candidates",
    elapsedS: 0.4,
    emptyReason: null,
    emptyFilter: null,
    problem: null,
    ...overrides,
  };
}

function view(props: Partial<Parameters<typeof ResultsView>[0]> = {}) {
  const handlers = { onRetry: vi.fn(), onEdit: vi.fn(), onRerun: vi.fn() };
  render(<ResultsView data={data()} answers={answers} error={null} online {...handlers} {...props} />);
  return handlers;
}

describe("C5 results for a meal now", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("cards show the server's strings only, and open the recipe in this search", () => {
    view();
    const card = screen.getByRole("article");
    expect(within(card).getByRole("link", { name: "Everyday chicken curry" })).toHaveAttribute("href", expect.stringMatching(/^\/recipe\/?\?version=21&search=5$/));
    expect(within(card).getByText("540 kcal · 41 g protein · 35 min · $2.10 a portion est. · $1.29 est. to buy today")).toBeInTheDocument(); // M12
    expect(within(card).getByText("Uses: chicken thigh, boneless skinless, spinach")).toBeInTheDocument();
    expect(within(card).getByText("Could buy: chickpeas $1.29 est. (Stop & Shop)")).toBeInTheDocument();
    expect(within(card).getByText("Swap: red onion instead of yellow onion (you have it)")).toBeInTheDocument(); // M11
    expect(within(card).getByText("ready in 35 min")).toBeInTheDocument();
    expect(within(card).queryByText(/Uses \d+ of your items/)).toBeNull(); // the Uses line already names them
    // no number on the card that the server didn't send
    const numbers = card.textContent?.match(/\d+(\.\d+)?/g) ?? [];
    const sent = JSON.stringify(suggestion());
    for (const n of numbers) expect(sent).toContain(n);
  });

  it("More ideas is shown disabled with 'coming soon' until step 2b.3b", () => {
    view();
    const more = screen.getByRole("button", { name: "More ideas" });
    expect(more).toBeDisabled();
    expect(more).toHaveAccessibleDescription("New recipe ideas: coming soon.");
  });

  it("shows the top 12, then Show more", async () => {
    const many = Array.from({ length: 14 }, (_, i) => suggestion({ version_id: i + 1, recipe_id: i + 1, title: `Recipe ${i + 1}` }));
    view({ data: data({ suggestions: many }) });
    expect(screen.getAllByRole("article")).toHaveLength(12);
    await userEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(screen.getAllByRole("article")).toHaveLength(14);
  });

  it("Edit goes back to the questions", async () => {
    const { onEdit } = view();
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalled();
  });

  it("empty: Pottle's reason and the buttons from the filter that removed the most", async () => {
    const { onRerun } = view({ data: data({ suggestions: [], emptyReason: "Nothing fits 20 minutes.", emptyFilter: "time" }) });
    expect(screen.getByText("Nothing fits 20 minutes.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Allow 30 min" }));
    expect(onRerun).toHaveBeenCalledWith(expect.objectContaining({ time_limit_minutes: 30, mood: "fancy" }));
    expect(screen.getByRole("button", { name: "Write new recipes (coming soon)" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "More ideas" })).not.toBeInTheDocument();
    expect(emptyFixes("time", { ...answers, time_limit_minutes: 120 }).map((f) => f.label)).toEqual(["Write new recipes (coming soon)"]);
    expect(emptyFixes("equipment", answers)[0]).toEqual({ label: "Check your equipment", href: "/settings/" });
  });

  it("mood is a preference: your mood's recipes first, then 'A bit more effort' and 'Simpler options' (M10)", () => {
    const cards = [
      suggestion({ version_id: 1, recipe_id: 1, title: "In your mood", section: "match" }),
      suggestion({ version_id: 2, recipe_id: 2, title: "Fancier", section: "more_effort" }),
      suggestion({ version_id: 3, recipe_id: 3, title: "Simpler", section: "simpler" }),
    ];
    view({ data: data({ suggestions: cards }) });
    const effort = screen.getByRole("region", { name: "A bit more effort" });
    expect(within(effort).getByRole("heading", { name: "A bit more effort" })).toBeInTheDocument();
    expect(within(effort).getByRole("link", { name: "Fancier" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Simpler options" })).getByRole("link", { name: "Simpler" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "In your mood" })).getByRole("link", { name: "In your mood" })).toBeInTheDocument();
    const order = screen.getAllByRole("article").map((a) => within(a).getByRole("link").textContent);
    expect(order).toEqual(["In your mood", "Fancier", "Simpler"]);
  });

  it("loading shows the building steps and skeleton cards", () => {
    view({ data: data({ suggestions: null, status: "running", stage: "constraints" }) });
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Checking your pantry");
    expect(screen.getByRole("status", { name: "Loading recipes" })).toBeInTheDocument();
  });

  it("a lost stream keeps the results with a warning and Try again", async () => {
    const { onRetry } = view({ data: data({ status: "lost" }) });
    expect(screen.getByRole("alert")).toHaveTextContent("Lost the connection; these may be incomplete.");
    expect(screen.getByRole("article")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("an error before any results is the error pattern", () => {
    view({ data: data({ suggestions: null, status: "failed" }), error: new ApiError(422, "Check your answers", "pick up to two nutrition goals") });
    expect(screen.getByRole("heading", { name: "Check your answers" })).toBeInTheDocument();
    expect(screen.getByText("pick up to two nutrition goals")).toBeInTheDocument();
  });

  it("♥ toggles in place, optimistically", async () => {
    const calls = mockApi(() => ({ status: 204 }));
    view();
    await userEvent.click(screen.getByRole("button", { name: "Favorite Everyday chicken curry" }));
    expect(screen.getByRole("button", { name: "Remove Everyday chicken curry from favorites" })).toHaveAttribute("aria-pressed", "true");
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(["PUT /api/v1/recipes/11/favorite"]);
  });
});
