"use client";

import { useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { GoalTiles } from "@/components/ui/GoalTiles";
import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { Segmented } from "@/components/ui/Segmented";
import { Stepper } from "@/components/ui/Stepper";
import { TileGrid } from "@/components/ui/TileGrid";
import type { MealSlot, RecipeMood } from "@/lib/api/types";
import { guessSlot, type MealNowDraft, MOODS, QUICK_DEFAULT_MINUTES } from "@/lib/cook/answers";
import { SLOT_ICONS } from "@/lib/format/icons";
import { humanize, slotLabel } from "@/lib/format/labels";

import styles from "./Ask.module.css";

const MEALS: MealSlot[] = ["breakfast", "lunch", "dinner", "snack", "protein_dessert"];
export const MAX_PEOPLE = 8;

/** "Dinner for 1": the meal you picked (or the clock's guess) and the people (or your household). */
export function forLine(draft: Pick<MealNowDraft, "slot" | "people">, householdSize: number | null, now: Date = new Date()): string {
  return `${slotLabel(draft.slot ?? guessSlot(now))} for ${draft.people ?? householdSize ?? 1}`;
}

function ForSheet({ open, draft, householdSize, onChange, onClose }: { open: boolean; draft: MealNowDraft; householdSize: number | null; onChange: (draft: MealNowDraft) => void; onClose: () => void }) {
  const slot = draft.slot ?? guessSlot();
  return (
    <BottomSheet title="Which meal, for how many?" open={open} onClose={onClose}>
      <TileGrid
        label="Meal"
        tiles={MEALS.map((m) => ({ key: m, label: SLOT_ICONS[m]?.label ?? slotLabel(m), icon: SLOT_ICONS[m]?.emoji }))}
        selected={[slot]}
        onToggle={(key) => onChange({ ...draft, slot: key as MealSlot })}
      />
      <Stepper label="People" value={draft.people ?? householdSize ?? 1} min={1} max={MAX_PEOPLE} step={1} unit="people" onChange={(people) => onChange({ ...draft, people })} />
      <button type="button" className="btn btn-primary btn-block" onClick={onClose}>
        Done
      </button>
    </BottomSheet>
  );
}

/** C2 What are you in the mood for? Goal tiles (at most two nutrition goals; Quick shows "Ready in"), the mood,
 * and the "For" line. */
export function GoalsStep({ draft, householdSize, onChange, onBack, onNext }: { draft: MealNowDraft; householdSize: number | null; onChange: (draft: MealNowDraft) => void; onBack: () => void; onNext: () => void }) {
  const [sheet, setSheet] = useState(false);
  const quick = draft.goals.includes("quick");
  return (
    <QuestionScreen
      title="What are you in the mood for?"
      why="Time and mood rule recipes out; the goals change the order."
      progress={{ step: 1, total: 2 }}
      onBack={onBack}
      primaryLabel="Next"
      onPrimary={onNext}
    >
      <button type="button" className={styles.forLine} onClick={() => setSheet(true)}>
        {forLine(draft, householdSize)} <span aria-hidden="true">▸</span>
      </button>
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
      {draft.mood === null && <p className="small muted">Not picked: today&apos;s usual from your cook schedule.</p>}
      <ForSheet open={sheet} draft={draft} householdSize={householdSize} onChange={onChange} onClose={() => setSheet(false)} />
    </QuestionScreen>
  );
}
