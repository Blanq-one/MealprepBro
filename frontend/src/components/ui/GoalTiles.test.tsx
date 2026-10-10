import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import type { GoalKey } from "@/lib/format/icons";

import { GoalTiles, toggleGoal } from "./GoalTiles";

function Harness() {
  const [goals, setGoals] = useState<GoalKey[]>([]);
  return (
    <>
      <GoalTiles goals={goals} onChange={setGoals} />
      <output aria-label="goals">{goals.join(",")}</output>
    </>
  );
}

describe("goal tiles: at most two nutrition goals", () => {
  it("a third nutrition goal swaps out the oldest and says why", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: /High protein/ }));
    await userEvent.click(screen.getByRole("button", { name: /Cheap/ }));
    await userEvent.click(screen.getByRole("button", { name: /High carb/ }));
    expect(screen.getByLabelText("goals")).toHaveTextContent("protein,cheap,carb");
    expect(screen.queryByText("Pick up to two nutrition goals")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Iron rich/ }));
    expect(screen.getByText("Pick up to two nutrition goals")).toHaveAttribute("role", "status");
    expect(screen.getByLabelText("goals")).toHaveTextContent("cheap,carb,iron"); // protein (oldest) is out
    expect(screen.getByRole("button", { name: /High protein/ })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /Iron rich/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Cheap/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("other goals don't count toward the limit, and the first nutrition goal is the primary one", () => {
    let goals: GoalKey[] = [];
    for (const key of ["quick", "carb", "cheap", "low_calorie", "protein"] as GoalKey[]) goals = toggleGoal(goals, key).goals;
    expect(goals).toEqual(["quick", "carb", "cheap", "low_calorie", "protein"]);
    expect(goals.find((g) => ["protein", "carb", "iron"].includes(g))).toBe("carb");
    expect(toggleGoal(goals, "carb")).toEqual({ goals: ["quick", "cheap", "low_calorie", "protein"], notice: null });
  });
});
