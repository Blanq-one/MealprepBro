"use client";

// The meal-prep questions (FLOW_SPEC §7): C1 How much, C1b How do you want to cook?, C2 goals and mood, and
// C3b Shopping for this? (C3 What do you have? is the meal-now screen's, HaveStep). One question per screen,
// pre-filled from your last meal-prep answers or your settings. They only edit the draft.
import Link from "next/link";

import { TierCards } from "@/components/cook/TierCards";
import { GoalTiles } from "@/components/ui/GoalTiles";
import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { Segmented } from "@/components/ui/Segmented";
import { BUDGET_SCALE, MoneySlider } from "@/components/ui/Slider";
import { Stepper } from "@/components/ui/Stepper";
import { TileGrid } from "@/components/ui/TileGrid";
import type { MealSlot, RecipeMood, UserSettings } from "@/lib/api/types";
import { MOODS, QUICK_DEFAULT_MINUTES } from "@/lib/cook/answers";
import {
  amountOf,
  amountProblems,
  buildPrepAnswers,
  choiceFor,
  type CookStyle,
  dayChipLabel,
  dayOf,
  defaultSessions,
  MAX_EXTRA_FREEZE,
  MAX_PREP_DAYS,
  MEAL_NAMES,
  planDays,
  PREP_MINUTES,
  PREP_STEPS,
  type PrepDraft,
  styleProblems,
  usualMinutes,
  withDayFix,
} from "@/lib/cook/prep";
import { toIso } from "@/lib/format/dates";
import { SLOT_ICONS } from "@/lib/format/icons";
import { humanize, minutesLabel } from "@/lib/format/labels";

import styles from "./PrepSteps.module.css";

type StepProps = {
  draft: PrepDraft;
  settings: UserSettings | null;
  onChange: (draft: PrepDraft) => void;
  onBack: () => void;
  onNext: () => void;
  today?: Date;
};

const TOTAL = PREP_STEPS.length;
const MEAL_SLOTS: MealSlot[] = ["breakfast", "lunch", "dinner", "snack", "protein_dessert"];

function mealTiles(settings: UserSettings | null) {
  const planned = new Set((settings?.slot_allocations ?? []).map((a) => a.slot));
  return MEAL_SLOTS.map((slot) => ({
    key: slot,
    label: MEAL_NAMES[slot] ?? slot,
    icon: SLOT_ICONS[slot]?.emoji,
    hint: settings && !planned.has(slot) ? "no calories set" : undefined,
  }));
}

/** Day buttons in one wrapping row: one choice (or several with `multi`). Each is a 48 px target. */
export function DayChips({ label, days, selected, onToggle, today }: { label: string; days: readonly string[]; selected: readonly string[]; onToggle: (day: string) => void; today: Date }) {
  return (
    <div className={styles.chips} role="group" aria-label={label}>
      {days.map((day) => {
        const on = selected.includes(day);
        return (
          <button key={day} type="button" className={on ? `${styles.chip} ${styles.on}` : styles.chip} aria-pressed={on} onClick={() => onToggle(day)}>
            {on && <span aria-hidden="true">✓ </span>}
            {dayChipLabel(day, today)}
          </button>
        );
      })}
    </div>
  );
}

// ---------------- C1 How much are you prepping? ----------------
const PRESETS = [
  { key: "five_lunches", label: "5 lunches", icon: "🥪" },
  { key: "lunch_dinner_5", label: "Lunch + dinner, 5 days", icon: "🍱" },
  { key: "usual_week", label: "My usual week", icon: "🗓️" },
  { key: "custom", label: "Something else", icon: "✏️" },
] as const;
// AA6: the tier cards are a quick estimate; the plan you build is solved in full
export const TIER_NOTE = "Totals are estimates for this week; the plan you build works out the exact list.";
// AA2: these portions aren't eaten in this plan; they go straight to the freezer
export const FREEZER_EXTRA_NOTE = "Extra portions go straight into the freezer for later weeks; they aren't part of this plan's meals.";

export function AmountStep({ draft, settings, onChange, onBack, onNext, today = new Date() }: StepProps) {
  const { reasons, missing } = amountProblems(draft, settings);
  const starts = Array.from({ length: MAX_PREP_DAYS }, (_, i) => {
    const day = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    day.setDate(day.getDate() + i);
    return toIso(day);
  });
  const start = dayOf(draft.start, today);
  return (
    <QuestionScreen
      title="How much are you prepping?"
      why="I'll scale the recipes to exactly this and plan what goes in the fridge or freezer."
      progress={{ step: 1, total: TOTAL }}
      onBack={onBack}
      primaryLabel="Next"
      onPrimary={onNext}
      primaryDisabled={reasons.length > 0}
      reasons={reasons}
      footerNote={
        missing.length > 0 ? (
          <Link href="/settings/edit/?field=meals">Set the calories for {missing.map((s) => (MEAL_NAMES[s] ?? s).toLowerCase()).join(" and ")}</Link>
        ) : undefined
      }
    >
      <TileGrid label="How much" tiles={PRESETS.map((p) => ({ key: p.key, label: p.label, icon: p.icon }))} selected={draft.preset ? [draft.preset] : []} onToggle={(key) => onChange({ ...draft, preset: key as PrepDraft["preset"] })} />
      {draft.preset === "custom" && (
        <>
          <Segmented
            label="Something else"
            options={[
              { value: "portions", label: "By portions" },
              { value: "days", label: "By days" },
            ]}
            value={draft.shape}
            onChange={(shape) => onChange({ ...draft, shape })}
          />
          {draft.shape === "portions" ? (
            <>
              <Stepper size="compact" label="Portions" value={draft.portions} min={1} max={MAX_PREP_DAYS} step={1} unit={draft.portions === 1 ? "portion" : "portions"} onChange={(portions) => onChange({ ...draft, portions })} />
              <TileGrid label="Meal" tiles={mealTiles(settings)} selected={draft.slot ? [draft.slot] : []} onToggle={(key) => onChange({ ...draft, slot: key as MealSlot })} />
              <p className="small muted">One meal on that many days in a row. More than {MAX_PREP_DAYS}? Cook the rest as extra for the freezer.</p>
            </>
          ) : (
            <>
              <Stepper size="compact" label="Days" value={draft.dayCount} min={1} max={MAX_PREP_DAYS} step={1} unit={draft.dayCount === 1 ? "day" : "days"} onChange={(dayCount) => onChange({ ...draft, dayCount })} />
              <TileGrid
                label="Meals"
                tiles={mealTiles(settings)}
                selected={draft.slots}
                onToggle={(key) => {
                  const slot = key as MealSlot;
                  onChange({ ...draft, slots: draft.slots.includes(slot) ? draft.slots.filter((s) => s !== slot) : [...draft.slots, slot] });
                }}
              />
            </>
          )}
        </>
      )}
      <p className={styles.label}>Starting</p>
      <DayChips label="Starting" days={starts.slice(0, 7)} selected={[start]} today={today} onToggle={(day) => onChange({ ...draft, start: choiceFor(day, today), sessions: [], cookDay: null })} />
      <Stepper size="compact" label="Cook extra for the freezer (future weeks)" value={draft.extraToFreeze} min={0} max={MAX_EXTRA_FREEZE} step={1} unit={draft.extraToFreeze === 1 ? "portion" : "portions"} onChange={(extraToFreeze) => onChange({ ...draft, extraToFreeze })} />
      <p className="small muted">{FREEZER_EXTRA_NOTE}</p>
    </QuestionScreen>
  );
}

// ---------------- C1b How do you want to cook? ----------------
const STYLES: { key: CookStyle | "basics"; label: string; icon: string; hint?: string }[] = [
  { key: "big_day", label: "One big cook day", icon: "🍲" },
  { key: "sessions", label: "A few sessions", icon: "🗓️" },
  { key: "same_dish", label: "Same dish, many portions", icon: "🍛" },
  { key: "mix", label: "Mix it up", icon: "🔀" },
  { key: "basics", label: "Cook basics, mix and match", icon: "🧺", hint: "coming soon" },
];

export function CookStyleStep({ draft, settings, onChange, onBack, onNext, today = new Date() }: StepProps) {
  const days = planDays(draft, settings, today);
  const cookDay = dayOf(draft.cookDay ?? draft.start, today);
  const minutes = draft.cookMinutes ?? usualMinutes(settings, cookDay);
  const portions = amountOf(draft, settings).portions;
  const reasons = styleProblems(draft);

  function pick(key: string) {
    const style = key as CookStyle;
    if (style === "sessions" && draft.sessions.length === 0) onChange({ ...draft, style, sessions: defaultSessions(days, settings) });
    else onChange({ ...draft, style });
  }

  return (
    <QuestionScreen
      title="How do you want to cook?"
      why="Cooked food keeps 3 days in the fridge, so anything past that goes in the freezer."
      progress={{ step: 2, total: TOTAL }}
      onBack={onBack}
      primaryLabel="Next"
      onPrimary={onNext}
      primaryDisabled={reasons.length > 0}
      reasons={reasons}
    >
      <TileGrid label="How to cook" tiles={STYLES.map((s) => ({ key: s.key, label: s.label, icon: s.icon, hint: s.hint, disabled: s.key === "basics" }))} selected={draft.style ? [draft.style] : []} onToggle={pick} />
      {(draft.style === "big_day" || draft.style === "same_dish") && (
        <>
          <p className={styles.label}>Cook on</p>
          <DayChips label="Cook on" days={days} selected={[cookDay]} today={today} onToggle={(day) => onChange({ ...draft, cookDay: choiceFor(day, today), cookMinutes: null })} />
          <Stepper label="Time in the kitchen" value={minutes} {...PREP_MINUTES} unit="start to finish" format={(v) => minutesLabel(v)} onChange={(cookMinutes) => onChange({ ...draft, cookMinutes })} />
          {draft.style === "big_day" ? (
            <p className="small muted">Everything is cooked that day. Dishes cook side by side, so the day can take more than your usual minutes.</p>
          ) : (
            <p className="small muted">
              One recipe for all {portions} portions{draft.extraToFreeze ? `, plus ${draft.extraToFreeze} extra for the freezer` : ""}.
            </p>
          )}
        </>
      )}
      {draft.style === "sessions" && (
        <>
          <p className={styles.label}>Cook days</p>
          <DayChips
            label="Cook days"
            days={days}
            selected={draft.sessions.map((s) => s.day)}
            today={today}
            onToggle={(day) => {
              const on = draft.sessions.some((s) => s.day === day);
              const next = on ? draft.sessions.filter((s) => s.day !== day) : [...draft.sessions, { day, minutes: usualMinutes(settings, day) }];
              onChange({ ...draft, sessions: next.sort((a, b) => (a.day < b.day ? -1 : 1)) });
            }}
          />
          {draft.sessions.filter((s) => days.includes(s.day)).map((session) => (
            <Stepper
              key={session.day}
              size="compact"
              label={dayChipLabel(session.day, today)}
              value={session.minutes}
              {...PREP_MINUTES}
              unit="start to finish"
              format={(v) => minutesLabel(v)}
              onChange={(m) => onChange({ ...draft, sessions: draft.sessions.map((s) => (s.day === session.day ? { ...s, minutes: m } : s)) })}
            />
          ))}
          {draft.sessions
            .filter((s) => s.mood && days.includes(s.day))
            .map((s) => (
              <p key={`mood-${s.day}`} className="small muted">
                {dayChipLabel(s.day, today)}: {s.mood} recipes allowed
              </p>
            ))}
        </>
      )}
      {draft.style === "mix" && <p className="small muted">Your cook days and their minutes from Settings, with a variety of recipes.</p>}
    </QuestionScreen>
  );
}

// ---------------- C2 goals and mood (meal prep) ----------------
export function PrepGoalsStep({ draft, settings, onChange, onBack, onNext }: StepProps) {
  const quick = draft.goals.includes("quick");
  return (
    <QuestionScreen
      title="What are you in the mood for?"
      why="Goals change which recipes come first; Quick limits every cook day's time."
      progress={{ step: 3, total: TOTAL }}
      onBack={onBack}
      primaryLabel="Next"
      onPrimary={onNext}
    >
      <Stepper size="compact" label="People" value={draft.people ?? settings?.household_size ?? 1} min={1} max={8} step={1} unit="people" onChange={(people) => onChange({ ...draft, people })} />
      <p className={styles.label}>Goals</p>
      <GoalTiles goals={draft.goals} onChange={(goals) => onChange({ ...draft, goals })} />
      {quick && (
        <Stepper size="compact" label="Ready in" value={draft.quickMinutes ?? QUICK_DEFAULT_MINUTES} min={5} max={240} step={5} unit="min, start to finish" onChange={(quickMinutes) => onChange({ ...draft, quickMinutes })} />
      )}
      <p className={styles.label}>Mood</p>
      <Segmented<RecipeMood> label="Mood" options={MOODS.map((m) => ({ value: m, label: humanize(m) }))} value={draft.mood} onChange={(mood) => onChange({ ...draft, mood: mood === draft.mood ? null : mood })} />
      <p className="small muted">{draft.mood === null ? "Not picked: each cook day's usual mood from Settings." : "Every cook day uses this mood."}</p>
    </QuestionScreen>
  );
}

// ---------------- C3b Shopping for this? ----------------
export function ShopStep({ draft, settings, onChange, onBack, onNext, online, today = new Date() }: StepProps & { online: boolean }) {
  const shopping = draft.shopping;
  const tier = draft.priceTier;
  const reasons = shopping === null ? ["Pick one"] : shopping === "make_a_list" && tier === null ? ["Pick a tier or set your own limit"] : undefined;
  return (
    <QuestionScreen
      title="Shopping for this?"
      why="So I know whether to plan around a shop."
      progress={{ step: 5, total: TOTAL }}
      onBack={onBack}
      primaryLabel="Build my plan"
      onPrimary={onNext}
      primaryDisabled={!online || reasons !== undefined}
      reasons={reasons}
      footerNote={!online ? "Needs a connection" : undefined}
    >
      <TileGrid
        label="Shopping"
        tiles={[
          { key: "use_what_i_have", label: "Use what I have", icon: "🥫", hint: "plus your could-buy items" },
          { key: "make_a_list", label: "Make me a shopping list", icon: "🛒" },
        ]}
        selected={shopping ? [shopping] : []}
        onToggle={(key) => onChange({ ...draft, shopping: key as PrepDraft["shopping"], budgetCents: key === draft.shopping ? draft.budgetCents : null, priceTier: key === draft.shopping ? draft.priceTier : null })}
      />
      {shopping === "make_a_list" && (
        <>
          <p className={styles.label}>How do you want to shop this week?</p>
          <TierCards
            answers={buildPrepAnswers({ ...draft, priceTier: null }, settings, today)}
            selected={tier === "own" ? null : tier}
            online={online}
            onPick={(priceTier) => onChange({ ...draft, priceTier, budgetCents: null })}
            onFix={(fix) => onChange(withDayFix(draft, fix, settings, today))}
          />
          <p className="small muted">{TIER_NOTE}</p>
          {tier === "own" ? (
            <>
              <MoneySlider label="Budget for this trip" valueCents={draft.budgetCents} scale={BUDGET_SCALE} onChange={(budgetCents) => onChange({ ...draft, budgetCents })} />
              <p className="small muted">Long-life items like rice and protein powder are listed separately and don&apos;t count toward this.</p>
            </>
          ) : (
            <button type="button" className="btn btn-link" onClick={() => onChange({ ...draft, priceTier: "own" })}>
              Set my own limit
            </button>
          )}
        </>
      )}
      {shopping === "use_what_i_have" && <p className="small muted">I&apos;ll buy only your could-buy items. If that isn&apos;t enough, I&apos;ll say what a small top-up would buy.</p>}
    </QuestionScreen>
  );
}
