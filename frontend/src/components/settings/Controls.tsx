"use client";

// The large controls for each settings field. Onboarding (W1–W7) pairs some of them on one screen; each
// Settings editor (S1) shows one. They only edit the draft: saving, checking and every total is the API's.
import { type FormEvent, useState } from "react";

import { EQUIPMENT, EquipmentIcon } from "@/components/ui/EquipmentIcon";
import { Segmented } from "@/components/ui/Segmented";
import { BUDGET_SCALE, MoneySlider } from "@/components/ui/Slider";
import { Stepper } from "@/components/ui/Stepper";
import { TileGrid } from "@/components/ui/TileGrid";
import { VersionChoices } from "@/components/pantry/VersionChoices";
import { ToggleRow } from "@/components/ui/ToggleRow";
import type { CookDay, DietReview, Equipment, MealSlot, RecipeMood, SlotAllocation, Store, UserSettings } from "@/lib/api/types";
import { SLOT_ICONS, SLOT_ORDER } from "@/lib/format/icons";
import { grouped, slotLabel } from "@/lib/format/labels";
import {
  BAND_KCAL,
  COOK_MINUTES,
  DAILY_KCAL,
  FRIDGE_DAYS,
  PEOPLE,
  PORK_MEALS,
  PROTEIN_G,
  porkCap,
  SLOT_KCAL,
  SPLIT_SCALE,
  WEEKDAYS,
  WEEKNIGHT_MINUTES,
  withPorkMeals,
} from "@/lib/settings/fields";

import styles from "./Controls.module.css";

export type Change = (changes: Partial<UserSettings>) => void;
type Props = { settings: UserSettings; onChange: Change };

export function FieldMessages({ messages }: { messages?: readonly string[] }) {
  if (!messages || messages.length === 0) return null;
  return (
    <ul className={styles.messages} role="alert">
      {messages.map((m) => (
        <li key={m}>{m}</li>
      ))}
    </ul>
  );
}

// ---------------- You ----------------
export function PeopleControl({ settings, onChange }: Props) {
  const n = settings.household_size;
  return (
    <Stepper
      label="People"
      value={n}
      unit={n === 1 ? "person" : "people"}
      {...PEOPLE}
      onChange={(household_size) => onChange({ household_size })}
    />
  );
}

export function BudgetControl({ settings, onChange }: Props) {
  return (
    <MoneySlider
      label="Weekly grocery budget (optional)"
      valueCents={settings.default_budget_cents ?? null}
      scale={BUDGET_SCALE}
      onChange={(default_budget_cents) => onChange({ default_budget_cents })}
    />
  );
}

export function CaloriesControl({ settings, onChange }: Props) {
  return (
    <Stepper
      label="Calories a day"
      value={settings.daily_kcal_target}
      unit="kcal"
      {...DAILY_KCAL}
      onChange={(daily_kcal_target) => onChange({ daily_kcal_target })}
    />
  );
}

export function ProteinControl({ settings, onChange }: Props) {
  const value = settings.daily_protein_target_g;
  return (
    <Stepper
      label="Protein"
      value={value}
      unit={value === 0 ? undefined : "g a day"}
      format={(v) => (v === 0 ? "No target" : grouped(v))}
      {...PROTEIN_G}
      onChange={(daily_protein_target_g) => onChange({ daily_protein_target_g })}
    />
  );
}

// ---------------- Meals ----------------
/** Allocations in tile order, with one slot's calories set (added if it's new). */
function setSlotKcal(allocations: readonly SlotAllocation[], slot: MealSlot, kcal: number): SlotAllocation[] {
  const next = new Map(allocations.map((a) => [a.slot, a.kcal]));
  next.set(slot, kcal);
  return SLOT_ORDER.filter((s) => next.has(s)).map((s) => ({ slot: s, kcal: next.get(s) as number }));
}

function MealSteppers({
  settings,
  onChange,
  pending,
  onPendingChange,
}: Props & { pending: readonly MealSlot[]; onPendingChange: (pending: MealSlot[]) => void }) {
  const chosen = SLOT_ORDER.filter((s) => pending.includes(s) || settings.slot_allocations.some((a) => a.slot === s));
  return (
    <div className={styles.mealSteppers}>
      {chosen.map((slot) => {
        const kcal = settings.slot_allocations.find((a) => a.slot === slot)?.kcal ?? null;
        return (
          <Stepper
            key={slot}
            size="compact"
            label={slotLabel(slot)}
            value={kcal}
            unit="kcal"
            {...SLOT_KCAL}
            onChange={(value) => {
              onChange({ slot_allocations: setSlotKcal(settings.slot_allocations, slot, value) });
              if (pending.includes(slot)) onPendingChange(pending.filter((p) => p !== slot));
            }}
          />
        );
      })}
    </div>
  );
}

/** Meal tiles, then a stepper per chosen meal and the API's "planned" line. A newly added meal starts empty
 * (`pending`) and needs a value. */
export function MealsControl({
  settings,
  onChange,
  pending,
  onPendingChange,
  plannedLine,
}: Props & { pending: readonly MealSlot[]; onPendingChange: (pending: MealSlot[]) => void; plannedLine: string | null }) {
  const selected = SLOT_ORDER.filter((s) => pending.includes(s) || settings.slot_allocations.some((a) => a.slot === s));
  function toggle(slot: MealSlot) {
    if (selected.includes(slot)) {
      onChange({ slot_allocations: settings.slot_allocations.filter((a) => a.slot !== slot) });
      onPendingChange(pending.filter((p) => p !== slot));
    } else {
      onPendingChange([...pending, slot]);
    }
  }
  return (
    <>
      <TileGrid
        label="Meals to plan"
        tiles={SLOT_ORDER.map((s) => ({ key: s, label: SLOT_ICONS[s]?.label ?? slotLabel(s), icon: SLOT_ICONS[s]?.emoji }))}
        selected={selected}
        onToggle={(key) => toggle(key as MealSlot)}
      />
      <MealSteppers settings={settings} onChange={onChange} pending={pending} onPendingChange={onPendingChange} />
      {plannedLine && (
        <p className={styles.planned} aria-live="polite">
          {plannedLine}
        </p>
      )}
    </>
  );
}

export function MealCaloriesControl({ settings, onChange, plannedLine }: Props & { plannedLine: string | null }) {
  return (
    <>
      <MealSteppers settings={settings} onChange={onChange} pending={[]} onPendingChange={() => undefined} />
      {plannedLine && (
        <p className={styles.planned} aria-live="polite">
          {plannedLine}
        </p>
      )}
    </>
  );
}

export function CalorieModeControl({ settings, onChange }: Props) {
  return (
    <>
      <Segmented
        label="Calorie mode"
        options={[
          { value: "weekly", label: "Weekly" },
          { value: "strict_daily", label: "Strict daily" },
        ]}
        value={settings.calorie_mode}
        onChange={(calorie_mode) => onChange({ calorie_mode })}
      />
      <p className="small muted">
        {settings.calorie_mode === "weekly"
          ? "The week stays under its total, and each day stays close to your daily target."
          : "Every day stays under your daily target."}
      </p>
    </>
  );
}

/** "Each day within ±150 kcal": weekly mode only (hidden in strict mode, FLOW_SPEC §11). */
export function BandControl({ settings, onChange }: Props) {
  if (settings.calorie_mode !== "weekly") return null;
  return (
    <Stepper
      label="Each day within ±"
      value={settings.daily_band_kcal}
      unit="kcal"
      {...BAND_KCAL}
      onChange={(daily_band_kcal) => onChange({ daily_band_kcal })}
    />
  );
}

export function PortionSizeControl({ settings, onChange }: Props) {
  return (
    <Segmented
      label="Portion size"
      options={[
        { value: "small", label: "Small" },
        { value: "normal", label: "Normal" },
        { value: "large", label: "Large" },
        { value: "extra_large", label: "XL" },
      ]}
      value={settings.default_portion_size}
      onChange={(default_portion_size) => onChange({ default_portion_size })}
    />
  );
}

// ---------------- Cooking ----------------
function sameMinutes(schedule: readonly CookDay[]): number | null {
  const minutes = new Set(schedule.filter((d) => d.is_cook_day).map((d) => d.cook_minutes));
  return minutes.size === 1 ? ([...minutes][0] as number) : null;
}

/** Weekday tiles. A day you turn on gets the minutes your other cook days have. */
export function CookDaysControl({ settings, onChange, fallbackMinutes }: Props & { fallbackMinutes: number }) {
  const schedule = settings.cook_schedule;
  const shared = sameMinutes(schedule) ?? schedule.find((d) => d.is_cook_day)?.cook_minutes ?? fallbackMinutes;
  return (
    <TileGrid
      label="Cook days"
      tiles={WEEKDAYS.map((d) => ({ key: d.key, label: d.label }))}
      selected={schedule.filter((d) => d.is_cook_day).map((d) => d.weekday)}
      onToggle={(key) =>
        onChange({
          cook_schedule: schedule.map((d) =>
            d.weekday !== key ? d : d.is_cook_day ? { ...d, is_cook_day: false, cook_minutes: 0 } : { ...d, is_cook_day: true, cook_minutes: shared },
          ),
        })
      }
    />
  );
}

/** One stepper for every cook day; "Different each day" opens one per day. */
export function CookMinutesControl({ settings, onChange }: Props) {
  const schedule = settings.cook_schedule;
  const cookDays = schedule.filter((d) => d.is_cook_day);
  const shared = sameMinutes(schedule);
  const [perDay, setPerDay] = useState(shared === null && cookDays.length > 1);
  if (cookDays.length === 0) return <p className="small muted">Pick at least one cook day first.</p>;
  const setAll = (minutes: number) => onChange({ cook_schedule: schedule.map((d) => (d.is_cook_day ? { ...d, cook_minutes: minutes } : d)) });
  if (!perDay || cookDays.length === 1) {
    return (
      <>
        <Stepper
          label="Minutes, start to finish"
          value={shared ?? (cookDays[0] as CookDay).cook_minutes}
          unit="min per cook day"
          {...COOK_MINUTES}
          onChange={setAll}
        />
        {cookDays.length > 1 && (
          <button type="button" className="btn btn-link btn-block" onClick={() => setPerDay(true)}>
            Different each day
          </button>
        )}
      </>
    );
  }
  return (
    <>
      {cookDays.map((day) => (
        <Stepper
          key={day.weekday}
          size="compact"
          label={WEEKDAYS.find((w) => w.key === day.weekday)?.long ?? day.weekday}
          value={day.cook_minutes}
          unit="min"
          {...COOK_MINUTES}
          onChange={(minutes) =>
            onChange({ cook_schedule: schedule.map((d) => (d.weekday === day.weekday ? { ...d, cook_minutes: minutes } : d)) })
          }
        />
      ))}
      <button
        type="button"
        className="btn btn-link btn-block"
        onClick={() => {
          setAll((cookDays[0] as CookDay).cook_minutes);
          setPerDay(false);
        }}
      >
        Same every day
      </button>
    </>
  );
}

/** The weeknight time for finishing prepped meals (V7): every day, cook day or not; "Different each day" opens
 * one stepper per day. */
export function WeeknightControl({ settings, onChange }: Props) {
  const schedule = settings.cook_schedule;
  const values = new Set(schedule.map((d) => d.weeknight_minutes ?? 30));
  const [perDay, setPerDay] = useState(values.size > 1);
  const setAll = (minutes: number) => onChange({ cook_schedule: schedule.map((d) => ({ ...d, weeknight_minutes: minutes })) });
  if (!perDay) {
    return (
      <>
        <Stepper label="Minutes, start to finish" value={schedule[0]?.weeknight_minutes ?? 30} unit="min a day" {...WEEKNIGHT_MINUTES} onChange={setAll} />
        <button type="button" className="btn btn-link btn-block" onClick={() => setPerDay(true)}>
          Different each day
        </button>
      </>
    );
  }
  return (
    <>
      {schedule.map((day) => (
        <Stepper
          key={day.weekday}
          size="compact"
          label={WEEKDAYS.find((w) => w.key === day.weekday)?.long ?? day.weekday}
          value={day.weeknight_minutes ?? 30}
          unit="min"
          {...WEEKNIGHT_MINUTES}
          onChange={(minutes) => onChange({ cook_schedule: schedule.map((d) => (d.weekday === day.weekday ? { ...d, weeknight_minutes: minutes } : d)) })}
        />
      ))}
      <button
        type="button"
        className="btn btn-link btn-block"
        onClick={() => {
          setAll(schedule[0]?.weeknight_minutes ?? 30);
          setPerDay(false);
        }}
      >
        Same every day
      </button>
    </>
  );
}

const MOODS: { value: RecipeMood; label: string }[] = [
  { value: "simple", label: "Simple" },
  { value: "medium", label: "Medium" },
  { value: "fancy", label: "Fancy" },
];

export function MoodControl({ settings, onChange }: Props) {
  const cookDays = settings.cook_schedule.filter((d) => d.is_cook_day);
  return (
    <>
      {cookDays.map((day) => {
        const name = WEEKDAYS.find((w) => w.key === day.weekday)?.long ?? day.weekday;
        return (
          <div key={day.weekday}>
            <p className={styles.dayName}>{name}</p>
            <Segmented
              label={`${name} mood`}
              options={MOODS}
              value={day.mood}
              onChange={(mood) =>
                onChange({ cook_schedule: settings.cook_schedule.map((d) => (d.weekday === day.weekday ? { ...d, mood } : d)) })
              }
            />
          </div>
        );
      })}
    </>
  );
}

export function EquipmentControl({ settings, onChange }: Props) {
  return (
    <TileGrid
      label="Kitchen equipment"
      tiles={EQUIPMENT.map((e) => ({ key: e.key, label: e.label, icon: <EquipmentIcon name={e.key} /> }))}
      selected={settings.equipment}
      onToggle={(key) =>
        onChange({
          equipment: settings.equipment.includes(key as Equipment)
            ? settings.equipment.filter((e) => e !== key)
            : [...settings.equipment, key as Equipment],
        })
      }
    />
  );
}

export function FridgeDaysControl({ settings, onChange }: Props) {
  const n = settings.leftover_fridge_days;
  return (
    <Stepper
      label="Fridge days for leftovers"
      value={n}
      unit={n === 1 ? "day" : "days"}
      {...FRIDGE_DAYS}
      onChange={(leftover_fridge_days) => onChange({ leftover_fridge_days })}
    />
  );
}

// ---------------- Shopping ----------------
/** Store tiles: the order you tap is your preference order (1, 2…). New stores are added by name; they are
 * created on the server when the draft is saved. */
export function StoresControl({
  settings,
  onChange,
  stores,
  pending,
  onAddPending,
}: Props & { stores: readonly Store[]; pending: readonly string[]; onAddPending: (name: string) => void }) {
  const [name, setName] = useState("");
  const known = [...stores.map((s) => s.name), ...pending.filter((p) => !stores.some((s) => s.name.toLowerCase() === p.toLowerCase()))];
  function toggle(store: string) {
    const order = settings.store_order;
    onChange({ store_order: order.includes(store) ? order.filter((s) => s !== store) : [...order, store] });
  }
  function add(event: FormEvent) {
    event.preventDefault();
    const clean = name.trim().replace(/\s+/g, " ");
    if (!clean) return;
    const existing = known.find((k) => k.toLowerCase() === clean.toLowerCase());
    if (!existing) onAddPending(clean);
    const store = existing ?? clean;
    if (!settings.store_order.includes(store)) onChange({ store_order: [...settings.store_order, store] });
    setName("");
  }
  return (
    <>
      <TileGrid
        label="Stores"
        order
        tiles={known.map((s) => ({ key: s, label: s, icon: "🛒", hint: pending.includes(s) ? "new" : undefined }))}
        selected={settings.store_order}
        onToggle={toggle}
      />
      <form className={styles.addStore} onSubmit={add}>
        <label htmlFor="new-store" className="sr-only">
          Store name
        </label>
        <input id="new-store" placeholder="Add a store" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="btn" disabled={!name.trim()}>
          Add
        </button>
      </form>
    </>
  );
}

export function SplitThresholdControl({ settings, onChange }: Props) {
  return (
    <MoneySlider
      label="Separate-store trip only if it saves at least"
      valueCents={settings.store_split_min_savings_cents}
      scale={SPLIT_SCALE}
      onChange={(cents) => onChange({ store_split_min_savings_cents: cents ?? 0 })}
    />
  );
}

// ---------------- Diet ----------------
export function BeefCard() {
  return (
    <section className={`card ${styles.rule}`} aria-label="Beef">
      <div className="row-between">
        <strong>
        <span aria-hidden="true">🐄 </span>
        Beef: never
      </strong>
        <span className="badge" aria-label="Locked">
          🔒 Locked
        </span>
      </div>
      <p className="small muted">Includes broth, tallow, gelatin and bouillon from beef.</p>
    </section>
  );
}

export function PorkControl({ settings, onChange }: Props) {
  const meals = porkCap(settings)?.max_meals_per_week ?? 1;
  return (
    <section className={`card ${styles.rule}`} aria-label="Pork">
      <strong>
        <span aria-hidden="true">🐖 </span>
        Pork: up to
      </strong>
      <Stepper
        size="compact"
        label="Pork meals a week"
        value={meals}
        unit={meals === 1 ? "meal a week" : "meals a week"}
        format={(v) => (v === 0 ? "Never" : String(v))}
        {...PORK_MEALS}
        onChange={(n) => onChange({ frequency_caps: withPorkMeals(settings, n) })}
      />
      <p className="small muted">Trace pork, such as lard in tortillas, is always fine.</p>
    </section>
  );
}

/** Possibly-beef items: held until you allow one. A change is saved at once (an ingredient decision, not a
 * setting); offline the switches are off. */
/** A held item that comes in versions (J4): the versions with the label guidance. Your usual one is saved in
 * your settings (M3) and only pre-selects it when you add the item; it never allows the held item itself. */
function HeldVersions({ item, onUsual, disabled }: { item: DietReview; onUsual: (item: DietReview, key: string | null) => void; disabled?: boolean }) {
  if (!item.versions) return null;
  const usual = item.versions.usual ?? null;
  return (
    <details className={styles.versions}>
      <summary>Comes in versions{usual ? `: you usually buy ${item.versions.choices.find((c) => c.key === usual)?.label ?? usual}` : ""}</summary>
      <VersionChoices
        versions={item.versions}
        selected={usual}
        usual={usual}
        disabled={disabled}
        onPick={(choice) => onUsual(item, choice.key === usual || choice.ingredient_id === null ? null : choice.key)}
      />
      <p className="small muted">
        Picking your usual version pre-selects it when you add {item.name}. It doesn&apos;t allow {item.name} itself, which
        stays held until you allow it above.
      </p>
    </details>
  );
}

export function HeldItemsControl({
  items,
  onDecide,
  disabled,
  busyId,
  onUsual,
}: {
  items: readonly DietReview[];
  onDecide: (item: DietReview, allow: boolean) => void;
  disabled?: boolean;
  busyId?: number | null;
  /** Save your usual version of a held item (Settings, M3); without it the versions aren't shown. */
  onUsual?: (item: DietReview, key: string | null) => void;
}) {
  return (
    <section className={`card ${styles.rule}`} aria-label="Held items">
      <strong>
        <span aria-hidden="true">⏸️ </span>
        Held items
      </strong>
      <p className="small muted">These may come from beef, so they stay out until you allow them.</p>
      {items.length === 0 && <p className="small muted">Nothing is held.</p>}
      {items.map((item) => (
        <div key={item.ingredient_id}>
          <ToggleRow
            label={item.name}
            detail={item.note ?? undefined}
            badges={<span className={item.decision === "allowed" ? "badge badge-herb" : "badge badge-warn"}>{item.decision === "allowed" ? "Allowed" : "Held"}</span>}
            checked={item.decision === "allowed"}
            disabled={disabled || busyId === item.ingredient_id}
            onChange={(allow) => onDecide(item, allow)}
          />
          {onUsual && <HeldVersions item={item} onUsual={onUsual} disabled={disabled || busyId === item.ingredient_id} />}
        </div>
      ))}
    </section>
  );
}
