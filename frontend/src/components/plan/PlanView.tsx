"use client";

// C6 Results: meal prep, also the current-plan view (FLOW_SPEC §7 C6, H4, F23, §19.10, §20.4). Today first,
// then the following days; earlier days fold away. Each cook day lists its batches and where every portion
// goes ("cook once, eat many"), with its timeline; each meal row says where its portion comes from. Freeze,
// spoil and "left out" notes sit behind the one Prep notes row, never above the days. Every number and line
// is the server's.
import Link from "next/link";
import { useEffect, useState } from "react";

import { MealMore } from "@/components/cook/NotForMe";
import { SwapButton } from "@/components/plan/Swap";
import { GroceryChecklist } from "@/components/GroceryChecklist";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Emoji } from "@/components/ui/Emoji";
import { Segmented } from "@/components/ui/Segmented";
import { ErrorState, NeedsConnection, Skeleton } from "@/components/ui/States";
import { api, ApiError, describeError } from "@/lib/api/client";
import type { Batch, Day, GroceryList, Meal, PlanSummary, SwapResult } from "@/lib/api/types";
import { dayLabel, parseDay, todayIso, toIso } from "@/lib/format/dates";
import { dishIcon } from "@/lib/format/icons";
import { grouped, minutesLabel, slotLabel } from "@/lib/format/labels";
import { useApi } from "@/lib/hooks/useApi";
import { orderDays, type PlanTab, readPlanTab, savePlanTab } from "@/lib/plan/days";
import { mealKey, type SwappedAway } from "@/lib/plan/swap";

import styles from "./PlanView.module.css";

/** "Today · Wed 14", "Tomorrow · Thu 15", "Fri Oct 16". */
export function dayHeading(iso: string, today: string): string {
  const short = dayLabel(iso).replace(/^(\w+) \w+ (\d+)$/, "$1 $2");
  if (iso === today) return `Today · ${short}`;
  const next = parseDay(today);
  next.setDate(next.getDate() + 1);
  if (iso === toIso(next)) return `Tomorrow · ${short}`;
  return dayLabel(iso);
}

/** A meal row opens its batch's recipe (C8); an assembled meal opens the assembly's page. */
export function mealHref(meal: Meal): string {
  return meal.kind === "assembly" || meal.cook_batch_id === null || meal.cook_batch_id === undefined ? `/recipe/?version=${meal.recipe_version_id}` : `/recipe/?batch=${meal.cook_batch_id}`;
}

/** What a plan view needs for Swap (step 2b.6): the recipes swapped away per meal, the swapped-in meal to
 * highlight, and what to do with a swap's result. */
export type SwapProps = { away: SwappedAway; highlight: number | null; onSwapped: (result: SwapResult, meal: Meal) => void };

export function MealRow({ meal, online, planId, swap }: { meal: Meal; online: boolean; planId?: number; swap?: SwapProps | null }) {
  const icon = dishIcon(meal.dish_category);
  const highlighted = swap?.highlight !== null && swap?.highlight !== undefined && swap.highlight === meal.plan_meal_id;
  const [swapOpen, setSwapOpen] = useState(false);
  const swappable = swap && planId !== undefined && meal.kind !== "assembly" && meal.plan_meal_id ? swap : null;
  return (
    <li className={highlighted ? `${styles.mealRow} ${styles.swapped}` : styles.mealRow}>
      <Link href={mealHref(meal)} className={styles.meal}>
        <Emoji symbol={icon.emoji} label={icon.label} className={styles.mealIcon} />
        <span className={styles.mealText}>
          <span className={styles.slot}>{slotLabel(meal.slot)}</span>
          <span className={styles.mealTitle}>
            {meal.title}
            {meal.is_draft && <span className="badge badge-warn"> Draft</span>}
          </span>
          <span className={styles.numbers}>
            {meal.kcal} kcal · {meal.protein_g} g protein
          </span>
          {meal.source_display && <span className={meal.storage === "freezer" ? `${styles.source} ${styles.frozen}` : styles.source}>{meal.source_display}</span>}
          {meal.kind === "assembly" && (meal.components ?? []).length > 0 && (
            <span className={styles.parts}>{(meal.components ?? []).map((c) => `${c.portions_display} ${c.label}`).join(" · ")}</span>
          )}
          {meal.instruction && <span className={styles.instruction}>{meal.instruction}</span>}
        </span>
      </Link>
      {swappable && planId !== undefined && (
        <SwapButton planId={planId} meal={meal} away={swappable.away[mealKey(meal.eat_on, meal.slot)] ?? []} online={online} open={swapOpen} onOpenChange={setSwapOpen} onSwapped={swappable.onSwapped} />
      )}
      <MealMore recipeId={meal.recipe_id} title={meal.title} online={online} planMealId={meal.plan_meal_id} onSwap={swappable ? () => setSwapOpen(true) : undefined} />
    </li>
  );
}

/** "Cook Chicken over rice ×4 → Mon lunch, Tue dinner, Sat dinner (1 to the freezer)" (F23). */
export function BatchRow({ batch }: { batch: Batch }) {
  const icon = dishIcon(batch.dish_category);
  const stop = batch.stop_display && batch.stop_display !== "cooked" ? `, ${batch.stop_display}` : "";
  return (
    <li className={styles.batch}>
      <Link href={`/recipe/?batch=${batch.id}`} className={styles.batchLink}>
        <Emoji symbol={icon.emoji} label={icon.label} className={styles.mealIcon} />
        <span>
          <span className={styles.batchTitle}>
            Cook {batch.title} ×{batch.portions}
            {stop}
          </span>
          {batch.uses_display && <span className={styles.uses}>→ {batch.uses_display}</span>}
          <span className={styles.numbers}>
            {batch.portions_display}
            {batch.freezer_friendly ? " · Freezes well" : ""}
            {batch.status === "cooked" ? " · Cooked" : ""}
          </span>
        </span>
      </Link>
    </li>
  );
}

/** The cook day's timeline (§20.4), behind a tap, with Start cooking (the cook-day cooking mode). */
function Timeline({ day, planId }: { day: Day; planId: number }) {
  const lines = day.timeline ?? [];
  if (lines.length === 0) return null;
  return (
    <details className={styles.timeline}>
      <summary>Timeline{day.time_display ? ` · ${day.time_display}` : ""}</summary>
      <ol className={styles.lines}>
        {lines.map((line, i) => (
          <li key={`${line.at_min}-${i}`} className={line.kind === "done" ? styles.done : undefined}>
            <span className={styles.at}>{line.at_display}</span>
            <span>
              {line.text}
              {line.estimated ? <span className="muted small"> (estimated)</span> : null}
            </span>
          </li>
        ))}
      </ol>
      <Link href={`/cook/cooking/?plan=${planId}&day=${day.day}`} className="btn btn-primary btn-block">
        Start cooking
      </Link>
    </details>
  );
}

/** Swap works on a draft or current plan's meals from today on (a past meal stays as it was). */
export function canSwap(plan: PlanSummary, day: string, today: string): boolean {
  return (plan.status === "draft" || plan.status === "active") && plan.kind !== "single" && day >= today;
}

export function DayCard({ day, plan, today, online, swap = null }: { day: Day; plan: PlanSummary; today: string; online: boolean; swap?: SwapProps | null }) {
  const batches = plan.batches.filter((b) => b.cook_on === day.day);
  const swapping = swap && canSwap(plan, day.day, today) ? swap : null;
  return (
    <section className={`card ${styles.day}`} id={`day-${day.day}`} aria-label={dayHeading(day.day, today)}>
      <header className={styles.dayHead}>
        <h2 className={styles.dayTitle}>{dayHeading(day.day, today)}</h2>
        <p className={styles.dayNumbers}>
          {grouped(day.kcal)} kcal · {day.protein_g} g protein{day.cost_display ? ` · ${day.cost_display}` : ""}
        </p>
      </header>
      {(day.finish_tasks ?? []).length > 0 && (
        <ul className={`list ${styles.finish}`} aria-label="Finish today">
          {(day.finish_tasks ?? []).map((task) => (
            <li key={task.id}>
              <span>{task.text}</span>
              <span className={styles.numbers}>{task.time_display}</span>
            </li>
          ))}
        </ul>
      )}
      {(day.freeze_steps ?? []).map((text) => (
        <p key={text} className={`notice notice-safety ${styles.dayNote}`}>
          {text}
        </p>
      ))}
      {(day.thaw_notes ?? []).map((text) => (
        <p key={text} className={`notice ${styles.dayNote}`}>
          {text}
        </p>
      ))}
      {batches.length > 0 ? (
        <div className={styles.cook} aria-label="Cook today">
          <p className={styles.cookHead}>Cook{day.time_display ? ` · ${day.time_display}` : ""}</p>
          <ul className="list">
            {batches.map((b) => (
              <BatchRow key={b.id} batch={b} />
            ))}
          </ul>
          {(day.freeze_today ?? []).map((text) => (
            <p key={text} className={styles.freezeToday}>
              {text}
            </p>
          ))}
          <Timeline day={day} planId={plan.id} />
        </div>
      ) : (
        <p className={styles.nothing}>{day.cook_note}</p>
      )}
      <ul className={`list ${styles.meals}`} aria-label="Meals">
        {day.meals.map((meal) => (
          <MealRow key={`${meal.slot}-${meal.recipe_version_id}`} meal={meal} online={online} planId={plan.id} swap={swapping} />
        ))}
      </ul>
    </section>
  );
}

const NOTE_GROUPS = [
  { title: "To freeze", kinds: ["freeze", "freeze_portions"] },
  { title: "May spoil", kinds: ["spoil"] },
  { title: "About this plan", kinds: ["about"] },
] as const;

/** The one Prep notes row (H4, F23): its text from the API, the items behind a tap. */
export function PrepNotes({ plan }: { plan: PlanSummary }) {
  const [open, setOpen] = useState(false);
  const notes = plan.prep_notes;
  if (!notes) return null;
  return (
    <>
      <button type="button" className={styles.notesRow} onClick={() => setOpen(true)} aria-haspopup="dialog">
        <span>
          <strong>Prep notes:</strong> {notes.display}
        </span>
        <span aria-hidden="true">›</span>
      </button>
      <BottomSheet title="Prep notes" open={open} onClose={() => setOpen(false)}>
        {NOTE_GROUPS.map((group) => {
          const items = notes.items.filter((i) => (group.kinds as readonly string[]).includes(i.kind));
          if (items.length === 0) return null;
          return (
            <section key={group.title} aria-label={group.title} className={styles.noteGroup}>
              <h3>{group.title}</h3>
              <ul className="small">
                {items.map((item, i) => (
                  <li key={`${item.kind}-${i}`}>{item.text}</li>
                ))}
              </ul>
            </section>
          );
        })}
        <button type="button" className="btn btn-block" onClick={() => setOpen(false)}>
          Close
        </button>
      </BottomSheet>
    </>
  );
}

type Overlap = { plan_id: number; start: string; end: string; meals: number; message: string };

/** Use this plan (E6), with the "Replace your current plan?" sheet when it overlaps your active plan. */
export function UsePlan({ plan, online, onAccepted }: { plan: PlanSummary; online: boolean; onAccepted: (plan: PlanSummary) => void }) {
  const [busy, setBusy] = useState(false);
  const [overlap, setOverlap] = useState<Overlap[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  if (plan.status === "active") return <p className={styles.current}>This is your current plan ✓</p>;
  if (plan.status !== "draft") return null;

  async function accept(replace: boolean) {
    setBusy(true);
    setError(null);
    try {
      const out = await api<PlanSummary>(`/api/v1/plans/${plan.id}/accept${replace ? "?replace_overlapping=true" : ""}`, { method: "POST" });
      setOverlap(null);
      onAccepted(out);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && Array.isArray(e.body?.overlapping)) setOverlap(e.body.overlapping as Overlap[]);
      else setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.useBar}>
      {error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
      <button type="button" className="btn btn-primary btn-block" disabled={busy || !online} onClick={() => void accept(false)}>
        {busy ? "Saving…" : "Use this plan"}
      </button>
      {!online && <NeedsConnection />}
      <BottomSheet title="Replace your current plan?" open={overlap !== null} onClose={() => setOverlap(null)}>
        {(overlap ?? []).map((o) => (
          <p key={o.plan_id}>{o.message}</p>
        ))}
        <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => void accept(true)}>
          Replace it
        </button>
        <button type="button" className="btn btn-block" onClick={() => setOverlap(null)}>
          Keep my current plan
        </button>
      </BottomSheet>
    </div>
  );
}

/** The plan's grocery list exactly as on the Grocery tab, read-only here, with Open in Grocery (C6). */
function ShoppingList({ planId }: { planId: number }) {
  const list = useApi<GroceryList>(`/api/v1/plans/${planId}/grocery-list?group_by=store`);
  if (list.loading && !list.data) return <Skeleton cards={2} label="Loading the shopping list" />;
  if (!list.data) return <ErrorState error={list.error} onRetry={() => void list.reload()} />;
  return (
    <>
      <p className={styles.trip}>{list.data.cash_split_display}</p>
      <GroceryChecklist list={list.data} disabled onPatch={() => undefined} />
      <Link href={`/grocery/?plan=${planId}`} className="btn btn-block">
        Open in Grocery
      </Link>
    </>
  );
}

/** The whole C6 screen for a plan. `today` is your date ("YYYY-MM-DD"). */
export function PlanView({ plan, online, today = todayIso(), onAccepted, swap = null }: { plan: PlanSummary; online: boolean; today?: string; onAccepted: (plan: PlanSummary) => void; swap?: SwapProps | null }) {
  const [tab, setTab] = useState<PlanTab>("recipes");
  useEffect(() => setTab(readPlanTab()), []);
  const { upcoming, earlier } = orderDays(plan.days, today);
  const todayDay = plan.days.find((d) => d.day === today);
  const first = plan.days[0];
  const last = plan.days[plan.days.length - 1];
  const range = first && last ? (first.day === last.day ? dayLabel(first.day) : `${dayLabel(first.day)} – ${dayLabel(last.day)}`) : "";
  return (
    <>
      <header className={styles.header}>
        <h1 className={styles.title}>{plan.header ?? `Your plan · ${range}`}</h1>
        <p className={styles.totals}>
          {plan.costs.cash_split_display}
          {todayDay && todayDay.hands_on_minutes > 0 ? ` · ${minutesLabel(todayDay.hands_on_minutes)} hands-on today` : ""}
        </p>
      </header>
      <PrepNotes plan={plan} />
      <Segmented<PlanTab>
        label="Show"
        options={[
          { value: "recipes", label: "Recipes" },
          { value: "shopping", label: "Shopping list" },
        ]}
        value={tab}
        onChange={(next) => {
          setTab(next);
          savePlanTab(next);
        }}
      />
      {tab === "shopping" ? (
        <ShoppingList planId={plan.id} />
      ) : (
        <div className={styles.days}>
          {upcoming.map((day) => (
            <DayCard key={day.day} day={day} plan={plan} today={today} online={online} swap={swap} />
          ))}
          {earlier.length > 0 && (
            <details className={styles.earlier} open={upcoming.length === 0}>
              <summary>Earlier in this plan</summary>
              {earlier.map((day) => (
                <DayCard key={day.day} day={day} plan={plan} today={today} online={online} />
              ))}
            </details>
          )}
        </div>
      )}
      <UsePlan plan={plan} online={online} onAccepted={onAccepted} />
    </>
  );
}
