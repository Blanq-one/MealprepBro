import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BottomSheet } from "./BottomSheet";
import { BuildingSteps, clockLabel } from "./BuildingSteps";
import { Pottle, type PottleState } from "./Pottle";
import { RecipeCard } from "./RecipeCard";
import { EmptyState, ErrorState } from "./States";
import { ApiError } from "@/lib/api/client";

describe("the recipe card", () => {
  it("shows the server's strings only, with the dish icon and badges", () => {
    render(
      <RecipeCard
        href="/recipe/?version=3"
        recipe={{
          title: "Everyday chicken curry",
          dish_category: "curry",
          badges: ["favorite", "draft"],
          numbers: ["540 kcal", "41 g protein", "35 min", "$2.10"],
          uses: "Uses: chicken thigh, spinach, onion",
          could_buy: ["Could buy: chickpeas $1.29 (Stop & Shop)"],
          missing: ["Missing: lemon → lime juice (you have it)"],
          why: ["Uses 3 of your items", "ready in 35 min"],
        }}
        isFavorite
        isSaved={false}
        onToggleFavorite={() => undefined}
        onToggleSaved={() => undefined}
      />,
    );
    expect(screen.getByRole("img", { name: "Curry" })).toHaveTextContent("🍛");
    expect(screen.getByText("540 kcal · 41 g protein · 35 min · $2.10")).toBeInTheDocument();
    expect(screen.getByText("Favorite")).toBeInTheDocument();
    expect(screen.queryByText("Draft")).toBeNull(); // every seed is a draft: only the recipe page says so (E)
    expect(screen.getByText("Could buy: chickpeas $1.29 (Stop & Shop)")).toBeInTheDocument();
    expect(screen.getByText("Uses 3 of your items · ready in 35 min")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Remove Everyday chicken curry from favorites/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Save Everyday chicken curry for later/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("toggles call back without navigating", async () => {
    const fav = vi.fn();
    const save = vi.fn();
    render(
      <RecipeCard
        href="/recipe/?version=3"
        recipe={{ title: "Overnight oats", dish_category: "oats", badges: [], numbers: [] }}
        isFavorite={false}
        isSaved={false}
        onToggleFavorite={fav}
        onToggleSaved={save}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Favorite Overnight oats" }));
    await userEvent.click(screen.getByRole("button", { name: "Save Overnight oats for later" }));
    expect(fav).toHaveBeenCalledOnce();
    expect(save).toHaveBeenCalledOnce();
  });
});

describe("Pottle", () => {
  it.each(["idle", "working", "happy", "sleepy", "oops"] as PottleState[])("draws the %s state with a label", (state) => {
    render(<Pottle state={state} />);
    const svg = screen.getByRole("img");
    expect(svg).toHaveAttribute("data-state", state);
    expect(svg.getAttribute("aria-label")).toMatch(/Pottle/);
  });
});

describe("building steps", () => {
  it("lists the server's stages with their state, and a wait is a countdown, not an error", () => {
    render(
      <BuildingSteps
        stages={[
          { key: "pantry", label: "Checking your pantry", state: "done" },
          { key: "solving", label: "Balancing calories across the days", state: "current" },
          { key: "pricing", label: "Pricing your groceries", state: "pending" },
        ]}
        waitS={23}
        waitStartedAt={Date.now()}
        elapsedS={41}
      />,
    );
    expect(screen.getByText(/Balancing calories across the days…/).closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("status")).toHaveTextContent("The recipe service needs a short breather. Back in 0:23");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("0:41 elapsed")).toBeInTheDocument();
    expect(clockLabel(65)).toBe("1:05");
  });
});

describe("empty, error and sheet patterns", () => {
  it("empty: Pottle, one sentence, one action", () => {
    render(<EmptyState message="Nothing saved yet. Tap ♥ on a recipe you'd make again." action={{ label: "Plan a week", href: "/plan/new/" }} />);
    expect(screen.getByRole("img", { name: /Pottle/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Plan a week" })).toBeInTheDocument();
  });

  it("error: the problem in plain words, Try again, and the details", async () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError(503, "The planner is busy", "Try again in a minute.")} onRetry={retry} runId={12} />);
    expect(screen.getByRole("heading", { name: "The planner is busy" })).toBeInTheDocument();
    expect(screen.getByText("Try again in a minute.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Pottle, surprised" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();
    expect(screen.getByText("Run 12")).toBeInTheDocument();
  });

  it("a bottom sheet is a labelled dialog that closes on Escape", async () => {
    const close = vi.fn();
    render(
      <BottomSheet title="How much?" open onClose={close}>
        <p>Pick one</p>
      </BottomSheet>,
    );
    expect(screen.getByRole("dialog", { name: "How much?" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(close).toHaveBeenCalled();
  });
});
