"use client";

// S0 (FLOW_SPEC §10): grouped rows, each with its current value, each opening its editor. Values are the
// API's numbers and lines, formatted; the "planned" and summary lines come from POST /settings/preview.
import Link from "next/link";
import { useEffect, useState } from "react";

import { Segmented } from "@/components/ui/Segmented";
import type { SettingsOut, SummaryLine, UserSettings } from "@/lib/api/types";
import { grouped, minutesLabel, slotLabel } from "@/lib/format/labels";
import { formatCents } from "@/lib/format/money";
import { dailyCapsValue, porkCap, previewSettings, WEEKDAYS } from "@/lib/settings/fields";
import { readThemeChoice, saveThemeChoice, type ThemeChoice } from "@/lib/theme/theme";

import styles from "./SettingsList.module.css";

type Row = { field?: string; label: string; value: string; locked?: boolean };
type Group = { title: string; rows: Row[] };

const MOOD_LABELS: Record<string, string> = { simple: "Simple", medium: "Medium", fancy: "Fancy" };
const SIZE_LABELS: Record<string, string> = { small: "Small", normal: "Normal", large: "Large", extra_large: "Extra large" };

function cookMinutesValue(s: UserSettings): string {
  const minutes = new Set(s.cook_schedule.filter((d) => d.is_cook_day).map((d) => d.cook_minutes));
  if (minutes.size === 0) return "No cook days";
  return minutes.size === 1 ? `${minutesLabel([...minutes][0] as number)} start to finish` : "Different each day";
}

function moodsValue(s: UserSettings): string {
  const days = s.cook_schedule.filter((d) => d.is_cook_day);
  const moods = new Set(days.map((d) => d.mood));
  if (moods.size === 1) return `${MOOD_LABELS[[...moods][0] as string]} every cook day`;
  return days.map((d) => `${WEEKDAYS.find((w) => w.key === d.weekday)?.label} ${MOOD_LABELS[d.mood]?.toLowerCase()}`).join(", ");
}

/** The rows, grouped. The weekly band row exists only in weekly mode (hidden in strict mode, FLOW_SPEC §11). */
export function settingsGroups(out: SettingsOut, summary: Record<string, string>): Group[] {
  const s = out.settings;
  const held = (out.diet_review ?? []).filter((d) => d.decision === "held").length;
  const allowed = (out.diet_review ?? []).filter((d) => d.decision === "allowed").length;
  const prefs = out.preferences.filter((p) => p.preference === "exclude" || p.preference === "dislike");
  const pork = porkCap(s);
  return [
    {
      title: "You",
      rows: [
        { field: "household_size", label: "People", value: summary.people ?? String(s.household_size) },
        { field: "daily_kcal_target", label: "Calories per day", value: `${grouped(s.daily_kcal_target)} kcal` },
        { field: "daily_protein_target_g", label: "Protein target", value: s.daily_protein_target_g ? `${s.daily_protein_target_g} g a day` : "No target" },
        { field: "default_budget_cents", label: "Weekly budget", value: s.default_budget_cents != null ? `${formatCents(s.default_budget_cents)} (a starting point)` : "No limit" },
      ],
    },
    {
      title: "Meals",
      rows: [
        { field: "meals", label: "Meals to plan", value: s.slot_allocations.map((a) => slotLabel(a.slot)).join(", ") },
        { field: "meal_calories", label: "Calories per meal", value: summary.meals ?? s.slot_allocations.map((a) => `${slotLabel(a.slot)} ${grouped(a.kcal)}`).join(" · ") },
        {
          field: "calorie_mode",
          label: "Calorie mode",
          value: s.calorie_mode === "weekly" ? `Weekly · each day within ±${grouped(s.daily_band_kcal)} kcal` : "Strict daily",
        },
        { field: "default_portion_size", label: "Portion size", value: SIZE_LABELS[s.default_portion_size] ?? s.default_portion_size },
      ],
    },
    {
      title: "Cooking",
      rows: [
        { field: "cook_days", label: "Cook days", value: s.cook_schedule.filter((d) => d.is_cook_day).map((d) => WEEKDAYS.find((w) => w.key === d.weekday)?.label).join(", ") || "None" },
        { field: "cook_minutes", label: "Time per cook day", value: cookMinutesValue(s) },
        { field: "moods", label: "Mood per cook day", value: moodsValue(s) },
        { field: "equipment", label: "Kitchen equipment", value: summary.equipment ?? s.equipment.join(", ") },
        { field: "leftover_fridge_days", label: "Fridge days for leftovers", value: `${s.leftover_fridge_days} ${s.leftover_fridge_days === 1 ? "day" : "days"}` },
      ],
    },
    {
      title: "Shopping",
      rows: [
        { field: "stores", label: "Stores and their order", value: summary.stores ?? s.store_order.join(", ") },
        { field: "store_split", label: "Separate-store trip", value: `Only if it saves at least ${formatCents(s.store_split_min_savings_cents)}` },
      ],
    },
    {
      title: "Diet",
      rows: [
        { label: "Beef", value: "Never (includes broth, tallow and gelatin from beef)", locked: true },
        { field: "held_items", label: "Held items", value: `${held} held, ${allowed} allowed` },
        {
          field: "frequency_caps",
          label: "Frequency caps",
          value: pork ? (pork.max_meals_per_week === 0 ? "Pork: never" : `Pork: up to ${pork.max_meals_per_week} a week`) : `${(s.frequency_caps ?? []).length} caps`,
        },
        { field: "daily_amount_caps", label: "Daily caps", value: summary.daily_caps ?? dailyCapsValue(s) },
        { field: "preferences", label: "Excluded and disliked", value: prefs.length ? prefs.map((p) => p.name).join(", ") : "None" },
      ],
    },
    {
      title: "Kitchen staples",
      rows: [{ field: "always_have", label: "Always have", value: summary.always_have ?? ((s.always_have ?? []).join(", ") || "Nothing yet") }],
    },
  ];
}

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Match my phone" },
];

export function AppearanceControl() {
  const [choice, setChoice] = useState<ThemeChoice>("light");
  useEffect(() => setChoice(readThemeChoice()), []);
  return (
    <Segmented
      label="Appearance"
      options={THEMES}
      value={choice}
      onChange={(next) => {
        setChoice(next);
        saveThemeChoice(next);
      }}
    />
  );
}

export function SettingsList({ out, onSignOut }: { out: SettingsOut; onSignOut: () => void }) {
  const [summary, setSummary] = useState<Record<string, string>>({});
  useEffect(() => {
    let stale = false;
    previewSettings({})
      .then((preview) => {
        if (!stale) setSummary(Object.fromEntries(preview.summary.map((line: SummaryLine) => [line.key, line.value])));
      })
      .catch(() => undefined); // offline: the rows show the plain values
    return () => {
      stale = true;
    };
  }, [out]);

  return (
    <>
      {settingsGroups(out, summary).map((group) => (
        <section key={group.title} className={styles.group} aria-label={group.title}>
          <h2 className={styles.groupTitle}>{group.title}</h2>
          <ul className={`list card ${styles.rows}`}>
            {group.rows.map((row) => (
              <li key={row.label}>
                {row.field ? (
                  <Link href={`/settings/edit/?field=${row.field}`} className={styles.row}>
                    <span className={styles.text}>
                      <span className={styles.label}>{row.label}</span>
                      <span className={styles.value}>{row.value}</span>
                    </span>
                    <span className={styles.chevron} aria-hidden="true">
                      ›
                    </span>
                  </Link>
                ) : (
                  <div className={styles.row}>
                    <span className={styles.text}>
                      <span className={styles.label}>{row.label}</span>
                      <span className={styles.value}>{row.value}</span>
                    </span>
                    {row.locked && <span className="badge">🔒 Locked</span>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
      <section className={styles.group} aria-label="Appearance">
        <h2 className={styles.groupTitle}>Appearance</h2>
        <AppearanceControl />
      </section>
      <section className={styles.group} aria-label="Account">
        <h2 className={styles.groupTitle}>Account</h2>
        <button type="button" className="btn btn-block" onClick={onSignOut}>
          Sign out
        </button>
      </section>
    </>
  );
}
