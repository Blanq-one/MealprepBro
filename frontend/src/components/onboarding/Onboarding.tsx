"use client";

// First-run onboarding, W0–W8 (FLOW_SPEC §6, E10): nine screens, related questions paired, pre-filled from your
// saved settings. Answers stay in a device draft; each Continue checks the draft with POST /settings/preview;
// "Start cooking" saves it once (PUT /settings, after POST /stores for a store you typed in). "Skip, use my
// current settings" changes nothing but the onboarding flag (PATCH).
import { useCallback, useEffect, useRef, useState } from "react";

import {
  BeefCard,
  BudgetControl,
  CaloriesControl,
  CookDaysControl,
  CookMinutesControl,
  EquipmentControl,
  FieldMessages,
  HeldItemsControl,
  MealsControl,
  PeopleControl,
  PorkControl,
  ProteinControl,
  StoresControl,
} from "@/components/settings/Controls";
import { Pottle } from "@/components/ui/Pottle";
import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { inRange } from "@/components/ui/Stepper";
import { api } from "@/lib/api/client";
import type { DietReview, MealSlot, SettingsOut, Store, SummaryLine, UserSettings } from "@/lib/api/types";
import { slotLabel } from "@/lib/format/labels";
import { useApi } from "@/lib/hooks/useApi";
import { clearDraft, loadDraft, newDraft, type OnboardingDraft, previewBody, saveDraft } from "@/lib/onboarding/draft";
import {
  COOK_MINUTES,
  DAILY_KCAL,
  errorsByField,
  errorsFromProblem,
  type FieldErrors,
  messagesFor,
  PEOPLE,
  PORK_MEALS,
  porkCap,
  PROTEIN_G,
  previewSettings,
  SLOT_KCAL,
} from "@/lib/settings/fields";

import styles from "./Onboarding.module.css";

export const STEPS = ["welcome", "household", "targets", "meals", "cooking", "kitchen", "stores", "rules", "done"] as const;
export type Step = (typeof STEPS)[number];
const QUESTIONS = STEPS.slice(1, 8); // W1–W7 get progress dots

/** The settings fields each screen edits: a server error for one of them keeps you on that screen. */
export const SCREEN_FIELDS: Record<Step, readonly string[]> = {
  welcome: [],
  household: ["household_size", "default_budget_cents"],
  targets: ["daily_kcal_target", "daily_protein_target_g"],
  meals: ["slot_allocations"],
  cooking: ["cook_schedule"],
  kitchen: ["equipment"],
  stores: ["store_order"],
  rules: ["frequency_caps"],
  done: [],
};

/** Summary rows (W8) -> the screen each one taps back to. */
const SUMMARY_STEP: Record<string, Step | undefined> = {
  people: "household",
  budget: "household",
  targets: "targets",
  meals: "meals",
  cook_days: "cooking",
  equipment: "kitchen",
  stores: "stores",
  food_rules: "rules",
};
const FIELD_SUMMARY: Record<string, string> = {
  household_size: "people",
  default_budget_cents: "budget",
  daily_kcal_target: "targets",
  daily_protein_target_g: "targets",
  slot_allocations: "meals",
  cook_schedule: "cook_days",
  equipment: "equipment",
  store_order: "stores",
  frequency_caps: "food_rules",
  always_have: "always_have",
};

export function isStep(value: string | null): value is Step {
  return value !== null && (STEPS as readonly string[]).includes(value);
}

/** Why Continue is still disabled on this screen (checked on the device; the server checks again). */
export function localReasons(step: Step, draft: OnboardingDraft): string[] {
  const s = draft.settings;
  const reasons: string[] = [];
  if (step === "household" && !inRange(s.household_size, PEOPLE.min, PEOPLE.max)) reasons.push("Pick how many people.");
  if (step === "targets") {
    if (!inRange(s.daily_kcal_target, DAILY_KCAL.min, DAILY_KCAL.max)) reasons.push("Pick your calories a day.");
    if (!inRange(s.daily_protein_target_g, PROTEIN_G.min, PROTEIN_G.max)) reasons.push("Pick your protein target.");
  }
  if (step === "meals") {
    if (s.slot_allocations.length === 0 && draft.pendingMeals.length === 0) reasons.push("Pick at least one meal.");
    for (const slot of draft.pendingMeals) reasons.push(`${slotLabel(slot)} needs its calories.`);
    if (s.slot_allocations.some((a) => !inRange(a.kcal, SLOT_KCAL.min, SLOT_KCAL.max))) reasons.push("Fix the calories for each meal.");
  }
  if (step === "cooking") {
    if (!s.cook_schedule.some((d) => d.is_cook_day)) reasons.push("Pick at least one cook day.");
    if (s.cook_schedule.some((d) => !inRange(d.cook_minutes, COOK_MINUTES.min, COOK_MINUTES.max))) reasons.push("Fix the minutes for each cook day.");
  }
  if (step === "kitchen" && s.equipment.length === 0) reasons.push("Pick at least one.");
  if (step === "stores" && s.store_order.length === 0) reasons.push("Pick at least one store.");
  if (step === "rules" && !inRange(porkCap(s)?.max_meals_per_week ?? 1, PORK_MEALS.min, PORK_MEALS.max)) reasons.push("Fix the pork meals a week.");
  return reasons;
}

function only(errors: FieldErrors, fields: readonly string[]): FieldErrors {
  return Object.fromEntries(Object.entries(errors).filter(([field]) => fields.includes(field)));
}

export type Navigate = (step: Step, how?: "push" | "back") => void;

export function Onboarding({ step, navigate, onDone, online }: { step: Step; navigate: Navigate; onDone: () => void; online: boolean }) {
  const loaded = useApi<SettingsOut>("/api/v1/settings");
  const stores = useApi<Store[]>("/api/v1/stores");
  const [draft, setDraft] = useState<OnboardingDraft | null>(null);
  const [diet, setDiet] = useState<DietReview[]>([]);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<unknown>(null);
  const [planned, setPlanned] = useState<string | null>(null);
  const [summary, setSummary] = useState<SummaryLine[] | null>(null);
  const [deciding, setDeciding] = useState<number | null>(null);
  const fallbackMinutes = useRef(30);

  useEffect(() => {
    if (!loaded.data) return;
    if (loaded.data.settings.onboarding_completed) {
      clearDraft();
      onDone();
      return;
    }
    setDiet(loaded.data.diet_review ?? []);
    setDraft((current) => current ?? loadDraft() ?? newDraft(loaded.data!.settings));
    fallbackMinutes.current = loaded.data.settings.cook_schedule.find((d) => d.is_cook_day)?.cook_minutes ?? 30;
  }, [loaded.data, onDone]);

  useEffect(() => {
    if (draft) saveDraft(draft);
  }, [draft]);

  // W3's live line ("1,800 of 1,800 kcal a day planned") and W8's summary come from the API.
  useEffect(() => {
    if (!draft || (step !== "meals" && step !== "done")) return;
    let stale = false;
    const timer = setTimeout(
      () => {
        previewSettings(previewBody(draft))
          .then((preview) => {
            if (stale) return;
            setPlanned(preview.kcal_planned_display);
            if (step === "meals") setErrors(only(errorsByField(preview.errors), SCREEN_FIELDS.meals));
            if (step === "done") setSummary(preview.summary);
          })
          .catch(() => undefined); // offline: no live line; Start cooking says it needs a connection
      },
      step === "meals" ? 300 : 0,
    );
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [draft, step]);

  const update = useCallback((changes: Partial<UserSettings>) => {
    setErrors({});
    setDraft((d) => (d ? { ...d, settings: { ...d.settings, ...changes } } : d));
  }, []);

  if (!draft) {
    if (loaded.error && !loaded.data) return <ErrorState error={loaded.error} onRetry={() => void loaded.reload()} />;
    return <Skeleton cards={3} label="Loading your settings" />;
  }

  const index = STEPS.indexOf(step);
  const prev = STEPS[index - 1];
  const next = STEPS[index + 1];
  const reasons = localReasons(step, draft);
  const s = draft.settings;

  async function proceed() {
    if (!draft || !next || localReasons(step, draft).length) return;
    setChecking(true);
    try {
      const preview = await previewSettings(previewBody(draft));
      const mine = only(errorsByField(preview.errors), SCREEN_FIELDS[step]);
      if (Object.keys(mine).length) {
        setErrors(mine);
        return;
      }
    } catch {
      // offline: you can step through; Start cooking needs the connection and checks everything
    } finally {
      setChecking(false);
    }
    setErrors({});
    navigate(next, "push");
  }

  async function skip() {
    setSaving(true);
    setProblem(null);
    try {
      await api<SettingsOut>("/api/v1/settings", { method: "PATCH", json: { onboarding_completed: true } });
      clearDraft();
      onDone();
    } catch (e) {
      setProblem(e);
    } finally {
      setSaving(false);
    }
  }

  async function decide(item: DietReview, allow: boolean) {
    setDeciding(item.ingredient_id);
    setProblem(null);
    try {
      const url = `/api/v1/settings/ingredient-preferences/${item.ingredient_id}`;
      if (allow) {
        const out = await api<SettingsOut>(url, { method: "PUT", json: { preference: "allow", reason: "allowed during setup" } });
        setDiet(out.diet_review ?? []);
      } else {
        await api(url, { method: "DELETE" });
        setDiet((items) => items.map((i) => (i.ingredient_id === item.ingredient_id ? { ...i, decision: "held" } : i)));
      }
    } catch (e) {
      setProblem(e);
    } finally {
      setDeciding(null);
    }
  }

  async function startCooking() {
    if (!draft) return;
    setSaving(true);
    setProblem(null);
    setErrors({});
    try {
      let order = draft.settings.store_order;
      for (const name of draft.newStores.filter((n) => order.includes(n))) {
        const store = await api<Store>("/api/v1/stores", { method: "POST", json: { name } });
        order = order.map((o) => (o === name ? store.name : o));
      }
      await api<SettingsOut>("/api/v1/settings", {
        method: "PUT",
        json: { ...draft.settings, store_order: order, onboarding_completed: true },
      });
      clearDraft();
      onDone();
    } catch (e) {
      const byField = errorsFromProblem(e);
      if (Object.keys(byField).length) setErrors(byField);
      else setProblem(e);
    } finally {
      setSaving(false);
    }
  }

  const back = prev ? () => navigate(prev, "back") : undefined;
  const progress = (QUESTIONS as readonly string[]).includes(step)
    ? { step: (QUESTIONS as readonly string[]).indexOf(step) + 1, total: QUESTIONS.length }
    : undefined;
  const common = {
    onBack: back,
    progress,
    primaryLabel: "Continue",
    onPrimary: () => void proceed(),
    primaryDisabled: reasons.length > 0,
    busy: checking,
    reasons: [...reasons, ...messagesFor(errors, ["settings"])],
  };
  const pendingMeals = draft.pendingMeals;
  const setPending = (meals: MealSlot[]) => setDraft((d) => (d ? { ...d, pendingMeals: meals } : d));

  switch (step) {
    case "welcome":
      return (
        <QuestionScreen
          title="Welcome to Mealbro"
          why="Let's set up your kitchen. It takes about a minute, and you can change anything later in Settings."
          primaryLabel="Let's go"
          onPrimary={() => navigate("household", "push")}
          footerNote={
            <>
              <button type="button" className="btn btn-link btn-block" onClick={() => void skip()} disabled={saving || !online}>
                Skip, use my current settings
              </button>
              {!online && <span>Skip needs a connection.</span>}
            </>
          }
        >
          <div className={styles.hero}>
            <Pottle state="idle" size={120} />
            <p className="muted">I&apos;m Pottle. I&apos;ll do the math; you do the cooking.</p>
          </div>
          {problem !== null && <ErrorState error={problem} title="Couldn't skip just now" />}
        </QuestionScreen>
      );
    case "household":
      return (
        <QuestionScreen title="Who are you cooking for?" why="I'll scale every recipe to match, and start each shopping plan with your budget." {...common}>
          <PeopleControl settings={s} onChange={update} />
          <FieldMessages messages={errors.household_size} />
          <p className="small muted">Your calorie and protein targets are for your portion; everyone gets the same size.</p>
          <BudgetControl settings={s} onChange={update} />
          <FieldMessages messages={errors.default_budget_cents} />
          <p className="small muted">A starting point: each shopping plan can set its own limit.</p>
        </QuestionScreen>
      );
    case "targets":
      return (
        <QuestionScreen title="Your daily targets" why="Every plan fits your calories and reaches at least your protein. Use the numbers that work for you." {...common}>
          <CaloriesControl settings={s} onChange={update} />
          <FieldMessages messages={errors.daily_kcal_target} />
          <ProteinControl settings={s} onChange={update} />
          <FieldMessages messages={errors.daily_protein_target_g} />
        </QuestionScreen>
      );
    case "meals":
      return (
        <QuestionScreen
          title="Which meals should I plan?"
          why="I'll only plan these. Each one aims for its calories; anything left over stays free for whatever you like."
          {...common}
        >
          <MealsControl settings={s} onChange={update} pending={pendingMeals} onPendingChange={setPending} plannedLine={planned} />
          <FieldMessages messages={errors.slot_allocations} />
        </QuestionScreen>
      );
    case "cooking":
      return (
        <QuestionScreen title="When do you cook?" why="On other days you'll eat what you cooked earlier. Simmering and chilling don't count against your time." {...common}>
          <CookDaysControl settings={s} onChange={update} fallbackMinutes={fallbackMinutes.current} />
          <CookMinutesControl settings={s} onChange={update} />
          <FieldMessages messages={errors.cook_schedule} />
        </QuestionScreen>
      );
    case "kitchen":
      return (
        <QuestionScreen title="What's in your kitchen?" why="I'll only suggest recipes you can make with these." {...common}>
          <EquipmentControl settings={s} onChange={update} />
          <FieldMessages messages={errors.equipment} />
        </QuestionScreen>
      );
    case "stores":
      return (
        <QuestionScreen title="Where do you shop?" why="Prices are kept per store, so I can show where something costs less." {...common}>
          <p className="small muted">Tap them in the order you prefer: 1 is where you shop most.</p>
          <StoresControl
            settings={s}
            onChange={update}
            stores={stores.data ?? []}
            pending={draft.newStores}
            onAddPending={(name) => setDraft((d) => (d ? { ...d, newStores: [...d.newStores, name] } : d))}
          />
          <FieldMessages messages={errors.store_order} />
        </QuestionScreen>
      );
    case "rules":
      return (
        <QuestionScreen title="Your food rules" why="These apply everywhere: recipes, plans and grocery lists." {...common}>
          <BeefCard />
          <PorkControl settings={s} onChange={update} />
          <FieldMessages messages={errors.frequency_caps} />
          <HeldItemsControl items={diet} onDecide={(item, allow) => void decide(item, allow)} disabled={!online} busyId={deciding} />
          {!online && <p className="small muted">Allowing a held item needs a connection.</p>}
          {problem !== null && <ErrorState error={problem} title="Couldn't change that item" />}
        </QuestionScreen>
      );
    case "done": {
      const newStoresLine =
        draft.newStores.some((n) => s.store_order.includes(n)) ? s.store_order.map((name, i) => `${i + 1} ${name}`).join(" · ") : null;
      return (
        <QuestionScreen
          title="All set"
          why="Here's what I'll work with."
          onBack={back}
          primaryLabel={online ? "Start cooking" : "Needs a connection to save"}
          onPrimary={() => void startCooking()}
          primaryDisabled={!online}
          busy={saving}
          reasons={messagesFor(errors, ["settings", "always_have"])}
        >
          <div className={styles.hero}>
            <Pottle state="happy" size={80} />
          </div>
          {summary === null && <Skeleton cards={1} label="Loading your summary" />}
          {summary && (
            <ul className={`list card ${styles.summary}`}>
              {summary
                .filter((line) => SUMMARY_STEP[line.key])
                .map((line) => {
                  const target = SUMMARY_STEP[line.key] as Step;
                  const rowErrors = Object.entries(errors)
                    .filter(([field]) => FIELD_SUMMARY[field] === line.key)
                    .flatMap(([, messages]) => messages);
                  return (
                    <li key={line.key}>
                      <button type="button" className={styles.summaryRow} onClick={() => navigate(target, "push")}>
                        <span className={styles.summaryLabel}>{line.label}</span>
                        <span>{line.key === "stores" && newStoresLine ? newStoresLine : line.value}</span>
                      </button>
                      <FieldMessages messages={rowErrors} />
                    </li>
                  );
                })}
            </ul>
          )}
          {problem !== null && <ErrorState error={problem} title="Couldn't save your settings" onRetry={() => void startCooking()} />}
        </QuestionScreen>
      );
    }
  }
}
