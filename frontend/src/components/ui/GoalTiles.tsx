"use client";

import { useState } from "react";

import { GOAL_ICONS, type GoalKey } from "@/lib/format/icons";

import { TileGrid } from "./TileGrid";

/** The nutrition goals: at most two, the first tapped is primary (FLOW_SPEC §7 C2). */
export const NUTRITION_GOALS: readonly GoalKey[] = ["protein", "carb", "iron"];
export const MAX_NUTRITION_GOALS = 2;
const GOAL_ORDER: readonly GoalKey[] = ["protein", "carb", "cheap", "quick", "iron", "low_calorie"];

export type GoalChange = { goals: GoalKey[]; notice: string | null };

/** Toggle one goal. A third nutrition goal swaps out the oldest one and says why. Order is kept: the first
 * nutrition goal in the list is the primary one. */
export function toggleGoal(goals: readonly GoalKey[], key: GoalKey): GoalChange {
  if (goals.includes(key)) return { goals: goals.filter((g) => g !== key), notice: null };
  const nutrition = goals.filter((g) => NUTRITION_GOALS.includes(g));
  if (NUTRITION_GOALS.includes(key) && nutrition.length >= MAX_NUTRITION_GOALS) {
    const oldest = nutrition[0];
    return { goals: [...goals.filter((g) => g !== oldest), key], notice: "Pick up to two nutrition goals" };
  }
  return { goals: [...goals, key], notice: null };
}

export function GoalTiles({ goals, onChange }: { goals: readonly GoalKey[]; onChange: (goals: GoalKey[]) => void }) {
  const [notice, setNotice] = useState<string | null>(null);
  return (
    <TileGrid
      label="Goals"
      tiles={GOAL_ORDER.map((key) => ({ key, label: GOAL_ICONS[key].label, icon: GOAL_ICONS[key].emoji }))}
      selected={goals}
      notice={notice}
      onToggle={(key) => {
        const change = toggleGoal(goals, key as GoalKey);
        setNotice(change.notice);
        onChange(change.goals);
      }}
    />
  );
}
