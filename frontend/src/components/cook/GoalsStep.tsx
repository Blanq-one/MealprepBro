"use client";

import { GoalTiles } from "@/components/ui/GoalTiles";
import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { Segmented } from "@/components/ui/Segmented";
import { Stepper } from "@/components/ui/Stepper";
import { TileGrid } from "@/components/ui/TileGrid";
import type { MealSlot, RecipeMood } from "@/lib/api/types";
import { type MealNowDraft, MOODS, QUICK_DEFAULT_MINUTES } from "@/lib/cook/answers";
import { SLOT_ICONS } from "@/lib/format/icons";
import { humanize } from "@/lib/format/labels";

import styles from "./Ask.module.css";

/** The meals you can cook now (M9), in the order of the day. Dessert is the protein dessert. */
export const MEALS: readonly { slot: MealSlot; label: string }[] = [
  { slot: "breakfast", label: "Breakfast" },
  { slot: "lunch", label: "Lunch" },
  { slot: "dinner", label: "Dinner" },
  { slot: "snack", label: "Snack" },
  { slot: "protein_dessert", label: "Dessert" },
];
export const MAX_PEOPLE = 8;
export const PICK_A_MEAL = "Pick a meal";

/** C2 What are you in the mood for? The meal (a visible choice, never guessed from the clock: M9), people,
 * goal tiles (at most two nutrition goals; Quick shows "Ready in") and the mood, a preference (M10). */
export function GoalsStep({ draft, householdSize, onChange, onBack, onNext }: { draft: MealNowDraft; householdSize: number | null; onChange: (draft: MealNowDraft) => void; onBack: () => void; onNext: () => void }) {
  const quick = draft.goals.includes("quick");
  return (
    <QuestionScreen
      title="What are you in the mood for?"
      why="Pick the meal; time rules recipes out, and the goals and mood change the order."
      progress={{ step: 1, total: 2 }}
      onBack={onBack}
      primaryLabel="Next"
      onPrimary={onNext}
      primaryDisabled={draft.slot === null}
      reasons={draft.slot === null ? [PICK_A_MEAL] : undefined}
    >
      <TileGrid
        label="Meal"
        tiles={MEALS.map((m) => ({ key: m.slot, label: m.label, icon: SLOT_ICONS[m.slot]?.emoji }))}
        selected={draft.slot ? [draft.slot] : []}
        onToggle={(key) => onChange({ ...draft, slot: key as MealSlot })}
      />
      <Stepper size="compact" label="People" value={draft.people ?? householdSize ?? 1} min={1} max={MAX_PEOPLE} step={1} unit="people" onChange={(people) => onChange({ ...draft, people })} />
      <p className={styles.label}>Goals</p>
      <GoalTiles goals={draft.goals} onChange={(goals) => onChange({ ...draft, goals })} />
      {quick && (
        <Stepper
          size="compact"
          label="Ready in"
          value={draft.quickMinutes ?? QUICK_DEFAULT_MINUTES}
          min={5}
          max={240}
          step={5}
          unit="min"
          onChange={(quickMinutes) => onChange({ ...draft, quickMinutes })}
        />
      )}
      <p className={styles.label}>Mood</p>
      <Segmented<RecipeMood>
        label="Mood"
        options={MOODS.map((m) => ({ value: m, label: humanize(m) }))}
        value={draft.mood}
        onChange={(mood) => onChange({ ...draft, mood: mood === draft.mood ? null : mood })}
      />
      <p className="small muted">
        {draft.mood === null ? "Not picked: today's usual from your cook schedule. " : ""}Recipes in your mood come first; the rest follow.
      </p>
    </QuestionScreen>
  );
}
