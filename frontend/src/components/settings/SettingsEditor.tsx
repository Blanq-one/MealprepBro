"use client";

// S1 (FLOW_SPEC §10): one setting at a time, on the same question screen and controls the wizard used, with
// Save. Save sends only that field (PATCH /settings); an error keeps your edit and shows the server's message
// under the control.
import { useEffect, useState } from "react";

import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { inRange } from "@/components/ui/Stepper";
import { api } from "@/lib/api/client";
import type { DietReview, MealSlot, SettingsOut, Store, UserSettings } from "@/lib/api/types";
import { slotLabel } from "@/lib/format/labels";
import { useApi } from "@/lib/hooks/useApi";
import {
  BAND_KCAL,
  CAP_MEALS,
  COOK_MINUTES,
  DAILY_KCAL,
  errorsFromProblem,
  type FieldErrors,
  FRIDGE_DAYS,
  messagesFor,
  PEOPLE,
  PROTEIN_G,
  SLOT_KCAL,
} from "@/lib/settings/fields";

import { AlwaysHaveEditor } from "./AlwaysHaveEditor";
import {
  BandControl,
  BudgetControl,
  CalorieModeControl,
  CaloriesControl,
  type Change,
  CookDaysControl,
  CookMinutesControl,
  EquipmentControl,
  FieldMessages,
  FridgeDaysControl,
  HeldItemsControl,
  MealCaloriesControl,
  MealsControl,
  MoodControl,
  PeopleControl,
  PortionSizeControl,
  ProteinControl,
  SplitThresholdControl,
  StoresControl,
} from "./Controls";
import { CapsControl, DailyCapsControl, PreferencesEditor } from "./DietEditors";
import { usePreview } from "./usePreview";

type Editor = {
  title: string;
  why: string;
  fields: (keyof UserSettings)[];
  /** Why Save is still disabled (checked on the phone; the server checks again). */
  invalid?: (s: UserSettings, pending: MealSlot[]) => string[];
};

const every = (ok: boolean, reason: string) => (ok ? [] : [reason]);

export const EDITORS: Record<string, Editor> = {
  household_size: {
    title: "How many people are you cooking for?",
    why: "I'll scale every recipe to match. Your targets are for your portion; everyone gets the same size.",
    fields: ["household_size"],
    invalid: (s) => every(inRange(s.household_size, PEOPLE.min, PEOPLE.max), "Pick how many people."),
  },
  daily_kcal_target: {
    title: "Calories a day",
    why: "Every plan fits your calories. Use the number that works for you.",
    fields: ["daily_kcal_target"],
    invalid: (s) => every(inRange(s.daily_kcal_target, DAILY_KCAL.min, DAILY_KCAL.max), "Pick your calories a day."),
  },
  daily_protein_target_g: {
    title: "Protein target",
    why: "Every plan reaches at least this much protein a day. 0 means no target.",
    fields: ["daily_protein_target_g"],
    invalid: (s) => every(inRange(s.daily_protein_target_g, PROTEIN_G.min, PROTEIN_G.max), "Pick your protein target."),
  },
  default_budget_cents: {
    title: "Weekly grocery budget",
    why: "A starting point for each shopping plan; every plan can set its own limit.",
    fields: ["default_budget_cents"],
  },
  meals: {
    title: "Which meals should I plan?",
    why: "I'll only plan these. Each one aims for its calories; anything left over stays free.",
    fields: ["slot_allocations"],
    invalid: (s, pending) => [
      ...every(s.slot_allocations.length > 0 || pending.length > 0, "Pick at least one meal."),
      ...pending.map((slot) => `${slotLabel(slot)} needs its calories.`),
    ],
  },
  meal_calories: {
    title: "Calories per meal",
    why: "Each meal aims for its calories; anything left over stays free for whatever you like.",
    fields: ["slot_allocations"],
    invalid: (s) => every(s.slot_allocations.every((a) => inRange(a.kcal, SLOT_KCAL.min, SLOT_KCAL.max)), "Fix the calories for each meal."),
  },
  calorie_mode: {
    title: "Calorie mode",
    why: "Weekly lets one day run a little over when another runs under; strict keeps every day under.",
    fields: ["calorie_mode", "daily_band_kcal"],
    invalid: (s) => every(s.calorie_mode !== "weekly" || inRange(s.daily_band_kcal, BAND_KCAL.min, BAND_KCAL.max), "Fix the daily range."),
  },
  default_portion_size: {
    title: "Portion size",
    why: "Larger portions keep the same calorie targets unless you raise them.",
    fields: ["default_portion_size"],
  },
  cook_days: {
    title: "Which days do you cook?",
    why: "On other days you'll eat what you cooked earlier.",
    fields: ["cook_schedule"],
    invalid: (s) => every(s.cook_schedule.some((d) => d.is_cook_day), "Pick at least one cook day."),
  },
  cook_minutes: {
    title: "Time per cook day",
    why: "Your time in the kitchen, start to finish. Dishes cook side by side, so a day fits more than its recipes one after another.",
    fields: ["cook_schedule"],
    invalid: (s) => every(s.cook_schedule.every((d) => inRange(d.cook_minutes, COOK_MINUTES.min, COOK_MINUTES.max)), "Fix the minutes for each cook day."),
  },
  moods: {
    title: "Mood per cook day",
    why: "Simple keeps hands-on time short; fancy allows more steps.",
    fields: ["cook_schedule"],
  },
  equipment: {
    title: "What's in your kitchen?",
    why: "I'll only suggest recipes you can make with these.",
    fields: ["equipment"],
    invalid: (s) => every(s.equipment.length > 0, "Pick at least one."),
  },
  leftover_fridge_days: {
    title: "Fridge days for leftovers",
    why: "Cooked food past this goes in the freezer. The FoodSafety.gov chart allows 4 days at most.",
    fields: ["leftover_fridge_days"],
    invalid: (s) => every(inRange(s.leftover_fridge_days, FRIDGE_DAYS.min, FRIDGE_DAYS.max), "Pick from 0 to 4 days."),
  },
  stores: {
    title: "Where do you shop?",
    why: "Prices are kept per store. Tap them in the order you prefer: 1 is where you shop most.",
    fields: ["store_order"],
    invalid: (s) => every(s.store_order.length > 0, "Pick at least one store."),
  },
  store_split: {
    title: "A separate-store trip",
    why: "I'll only suggest shopping at a second store when it saves at least this much that week.",
    fields: ["store_split_min_savings_cents"],
  },
  daily_amount_caps: {
    title: "Daily caps",
    why: "How much a day, counting every meal. Plans keep to the usual amount when another plan fits, and never go over the most.",
    fields: ["daily_amount_caps"],
    invalid: (s) =>
      every(
        (s.daily_amount_caps ?? []).every((c) => c.usual <= c.maximum && c.maximum > 0),
        "The usual amount can't be more than the most.",
      ),
  },
  frequency_caps: {
    title: "Frequency caps",
    why: "At most this many meals a week. Capped foods are never favored.",
    fields: ["frequency_caps"],
    invalid: (s) => every((s.frequency_caps ?? []).every((c) => inRange(c.max_meals_per_week, CAP_MEALS.min, CAP_MEALS.max)), "Fix the meals a week."),
  },
};

/** Editors that save each change at once (ingredient decisions) or have their own screen. */
export const SPECIAL_EDITORS = ["held_items", "preferences", "always_have"] as const;

export function isEditor(field: string | null): boolean {
  return field !== null && (field in EDITORS || (SPECIAL_EDITORS as readonly string[]).includes(field));
}

function control(field: string, s: UserSettings, onChange: Change, extra: { pending: MealSlot[]; setPending: (p: MealSlot[]) => void; planned: string | null; stores: Store[]; newStores: string[]; addStore: (n: string) => void; fallbackMinutes: number }) {
  switch (field) {
    case "household_size":
      return <PeopleControl settings={s} onChange={onChange} />;
    case "daily_kcal_target":
      return <CaloriesControl settings={s} onChange={onChange} />;
    case "daily_protein_target_g":
      return <ProteinControl settings={s} onChange={onChange} />;
    case "default_budget_cents":
      return <BudgetControl settings={s} onChange={onChange} />;
    case "meals":
      return <MealsControl settings={s} onChange={onChange} pending={extra.pending} onPendingChange={extra.setPending} plannedLine={extra.planned} />;
    case "meal_calories":
      return <MealCaloriesControl settings={s} onChange={onChange} plannedLine={extra.planned} />;
    case "calorie_mode":
      return (
        <>
          <CalorieModeControl settings={s} onChange={onChange} />
          <BandControl settings={s} onChange={onChange} />
        </>
      );
    case "default_portion_size":
      return <PortionSizeControl settings={s} onChange={onChange} />;
    case "cook_days":
      return <CookDaysControl settings={s} onChange={onChange} fallbackMinutes={extra.fallbackMinutes} />;
    case "cook_minutes":
      return <CookMinutesControl settings={s} onChange={onChange} />;
    case "moods":
      return <MoodControl settings={s} onChange={onChange} />;
    case "equipment":
      return <EquipmentControl settings={s} onChange={onChange} />;
    case "leftover_fridge_days":
      return <FridgeDaysControl settings={s} onChange={onChange} />;
    case "stores":
      return <StoresControl settings={s} onChange={onChange} stores={extra.stores} pending={extra.newStores} onAddPending={extra.addStore} />;
    case "store_split":
      return <SplitThresholdControl settings={s} onChange={onChange} />;
    case "frequency_caps":
      return <CapsControl settings={s} onChange={onChange} />;
    case "daily_amount_caps":
      return <DailyCapsControl settings={s} onChange={onChange} />;
    default:
      return null;
  }
}

function HeldItemsEditor({ onDone, online }: { onDone: () => void; online: boolean }) {
  const loaded = useApi<SettingsOut>("/api/v1/settings");
  const [items, setItems] = useState<DietReview[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [problem, setProblem] = useState<unknown>(null);
  useEffect(() => {
    if (loaded.data) setItems(loaded.data.diet_review ?? []);
  }, [loaded.data]);

  /** Your usual version of a held item, saved in your settings (M3); null forgets it. */
  async function usual(item: DietReview, key: string | null) {
    setBusy(item.ingredient_id);
    setProblem(null);
    try {
      const current = { ...(loaded.data?.settings.usual_versions ?? {}) };
      if (key === null) delete current[item.slug];
      else current[item.slug] = key;
      const out = await api<SettingsOut>("/api/v1/settings", { method: "PATCH", json: { usual_versions: current } });
      loaded.setData(out);
      setItems(out.diet_review ?? []);
    } catch (e) {
      setProblem(e);
    } finally {
      setBusy(null);
    }
  }

  async function decide(item: DietReview, allow: boolean) {
    setBusy(item.ingredient_id);
    setProblem(null);
    try {
      const url = `/api/v1/settings/ingredient-preferences/${item.ingredient_id}`;
      if (allow) setItems((await api<SettingsOut>(url, { method: "PUT", json: { preference: "allow", reason: "reviewed in the app" } })).diet_review ?? []);
      else {
        await api(url, { method: "DELETE" });
        setItems((list) => (list ?? []).map((i) => (i.ingredient_id === item.ingredient_id ? { ...i, decision: "held" } : i)));
      }
    } catch (e) {
      setProblem(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <QuestionScreen title="Held items" why="These may come from beef, so they stay out of plans until you allow one. Beef itself is always out." onBack={onDone} primaryLabel="Done" onPrimary={onDone}>
      {items === null ? (
        loaded.error ? <ErrorState error={loaded.error} onRetry={() => void loaded.reload()} /> : <Skeleton cards={2} />
      ) : (
        <HeldItemsControl items={items} onDecide={(item, allow) => void decide(item, allow)} onUsual={(item, key) => void usual(item, key)} disabled={!online} busyId={busy} />
      )}
      {!online && <p className="small muted">Changing a held item needs a connection.</p>}
      {problem !== null && <ErrorState error={problem} title="Couldn't change that item" />}
    </QuestionScreen>
  );
}

export function SettingsEditor({ field, onDone, online }: { field: string; onDone: () => void; online: boolean }) {
  const loaded = useApi<SettingsOut>("/api/v1/settings");
  const stores = useApi<Store[]>(field === "stores" ? "/api/v1/stores" : null);
  const [draft, setDraft] = useState<UserSettings | null>(null);
  const [pending, setPending] = useState<MealSlot[]>([]);
  const [newStores, setNewStores] = useState<string[]>([]);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<unknown>(null);
  const editor = EDITORS[field];
  const wantsPlanned = field === "meals" || field === "meal_calories";
  const preview = usePreview(draft && wantsPlanned ? { slot_allocations: draft.slot_allocations, daily_kcal_target: draft.daily_kcal_target } : null, wantsPlanned);

  useEffect(() => {
    if (loaded.data) setDraft((d) => d ?? loaded.data!.settings);
  }, [loaded.data]);

  if (field === "held_items") return <HeldItemsEditor onDone={onDone} online={online} />;
  if (field === "preferences") return <PreferencesEditor onDone={onDone} online={online} />;
  if (field === "always_have") return <AlwaysHaveEditor onDone={onDone} online={online} />;
  if (!editor) return <ErrorState error={new Error("There's no such setting.")} title="Not a setting" />;
  if (!draft) {
    if (loaded.error && !loaded.data) return <ErrorState error={loaded.error} onRetry={() => void loaded.reload()} />;
    return <Skeleton cards={2} label="Loading your settings" />;
  }

  const onChange: Change = (changes) => {
    setErrors({});
    setDraft((d) => (d ? { ...d, ...changes } : d));
  };
  const local = editor.invalid?.(draft, pending) ?? [];
  const shown = { ...preview.errors, ...errors };
  const fieldMessages = messagesFor(shown, editor.fields as string[]);

  async function save() {
    if (!draft || !editor) return;
    setSaving(true);
    setProblem(null);
    try {
      let changes: Partial<UserSettings> = Object.fromEntries(editor.fields.map((f) => [f, draft[f]]));
      if (field === "stores") {
        let order = draft.store_order;
        for (const name of newStores.filter((n) => order.includes(n))) {
          const store = await api<Store>("/api/v1/stores", { method: "POST", json: { name } });
          order = order.map((o) => (o === name ? store.name : o));
        }
        changes = { store_order: order };
      }
      await api<SettingsOut>("/api/v1/settings", { method: "PATCH", json: changes });
      onDone();
    } catch (e) {
      const byField = errorsFromProblem(e);
      if (Object.keys(byField).length) setErrors(byField);
      else setProblem(e);
    } finally {
      setSaving(false);
    }
  }

  const fallbackMinutes = loaded.data?.settings.cook_schedule.find((d) => d.is_cook_day)?.cook_minutes ?? 30;
  return (
    <QuestionScreen
      title={editor.title}
      why={editor.why}
      onBack={onDone}
      primaryLabel={online ? "Save" : "Needs a connection"}
      onPrimary={() => void save()}
      primaryDisabled={!online || local.length > 0}
      busy={saving}
      reasons={[...local, ...messagesFor(shown, ["settings"])]}
    >
      {control(field, draft, onChange, {
        pending,
        setPending,
        planned: preview.planned,
        stores: stores.data ?? [],
        newStores,
        addStore: (name) => setNewStores((s) => [...s, name]),
        fallbackMinutes,
      })}
      <FieldMessages messages={fieldMessages} />
      {problem !== null && <ErrorState error={problem} title="Couldn't save that" onRetry={() => void save()} />}
    </QuestionScreen>
  );
}
