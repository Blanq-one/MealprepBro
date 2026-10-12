"use client";

import Link from "next/link";

import { Pottle } from "@/components/ui/Pottle";
import type { PlanStreamEvent } from "@/lib/api/types";
import { weekdayName } from "@/lib/format/dates";
import { formatCents } from "@/lib/format/money";

import styles from "./NoPlanFits.module.css";

/** One problem diagnostic as the server sends it (planning/orchestrator.problem_json). */
export type PlanDiagnostic = {
  code?: string;
  message?: string;
  suggested_cents?: number;
  items?: string[];
  day?: string; // "YYYY-MM-DD"
  suggested_minutes?: number; // COOK_TIME_SHORT and COOK_TIME_TOO_SHORT: the minutes to allow (P4)
  mood?: string; // RECIPES_LEFT_OUT: the mood the left-out recipes need, e.g. "fancy"
};

export type FixActions = {
  /** Plan again from what you have, allowing this top-up. */
  onTopUp?: (cents: number) => void;
  /** Plan again with a shopping list. */
  onShop?: () => void;
  /** Plan again with this budget. */
  onBudget?: (cents: number) => void;
  /** Plan again allowing this many minutes, start to finish, on that day (or on every cook day: null). */
  onMinutes?: (day: string | null, minutes: number) => void;
  /** Plan again with this mood ("simple" = simpler recipes), on that day or every day (null). */
  onMood?: (day: string | null, mood: string) => void;
  /** The same answers again (new recipes are written for a meal with none). */
  onRetry?: () => void;
};

/** "$37" for a whole-dollar suggestion (formatting only: the server rounded it up). */
function dollars(cents: number): string {
  return formatCents(cents).replace(/\.00$/, "");
}

/** Settings a reason points at, when the fix is yours to make there. */
const SETTING_FIXES: Record<string, { label: string; href: string }> = {
  KCAL_DAY_BELOW_FLOOR: { label: "Change calories", href: "/settings/edit/?field=meal_calories" },
  KCAL_DAY_ABOVE_CEILING: { label: "Change calories", href: "/settings/edit/?field=meal_calories" },
  KCAL_WEEK_ABOVE_CEILING: { label: "Change calories", href: "/settings/edit/?field=meal_calories" },
  KCAL_WEEK_BELOW_FLOOR: { label: "Change calories", href: "/settings/edit/?field=meal_calories" },
  PROTEIN_SHORT: { label: "Change your protein target", href: "/settings/edit/?field=daily_protein_target_g" },
  HELD_INGREDIENTS: { label: "Review held items", href: "/settings/edit/?field=held_items" },
  FREQUENCY_CAP: { label: "Change frequency caps", href: "/settings/edit/?field=frequency_caps" },
  DAILY_AMOUNT_CAP: { label: "Change daily caps", href: "/settings/edit/?field=daily_amount_caps" },
};
const SHOWN = 3; // one to three reasons, the rest behind a tap (C6)

/** The reasons, each said once (never the same sentence twice). */
export function reasons(event: PlanStreamEvent): PlanDiagnostic[] {
  const all = (event.problem?.diagnostics ?? []) as PlanDiagnostic[];
  return all.filter((d, i) => all.findIndex((o) => o.message === d.message) === i);
}

function Fixes({ d, actions, busy, seen }: { d: PlanDiagnostic; actions: FixActions; busy: boolean; seen: Set<string> }) {
  const buttons: { label: string; primary?: boolean; run?: () => void; href?: string }[] = [];
  if (d.code === "INVENTORY_SHORT" && d.suggested_cents) {
    const cents = d.suggested_cents;
    if (actions.onTopUp) buttons.push({ label: `Allow a ${dollars(cents)} top-up`, primary: true, run: () => actions.onTopUp?.(cents) });
    if (actions.onShop) buttons.push({ label: "Switch to shopping", run: () => actions.onShop?.() });
  }
  if (d.code === "BUDGET_SHORT" && d.suggested_cents && actions.onBudget) {
    const cents = d.suggested_cents;
    buttons.push({ label: `Raise the budget to ${dollars(cents)}`, primary: true, run: () => actions.onBudget?.(cents) });
  }
  if ((d.code === "COOK_TIME_SHORT" || d.code === "COOK_TIME_TOO_SHORT") && d.suggested_minutes) {
    const minutes = d.suggested_minutes;
    const day = d.code === "COOK_TIME_SHORT" ? (d.day ?? null) : null;
    if (actions.onMinutes) buttons.push({ label: day ? `Allow ${minutes} min on ${weekdayName(day)}` : `Allow ${minutes} min`, primary: true, run: () => actions.onMinutes?.(day, minutes) });
    if (actions.onMood) buttons.push({ label: "Use simpler recipes", run: () => actions.onMood?.(day, "simple") });
  }
  if (d.code === "RECIPES_LEFT_OUT" && d.mood && actions.onMood) {
    const mood = d.mood;
    buttons.push({ label: `Allow ${mood} recipes`, run: () => actions.onMood?.(null, mood) });
  }
  if ((d.code === "NO_CANDIDATES_FOR_SLOT" || d.code === "SLOT_UNFILLABLE") && actions.onRetry) {
    buttons.push({ label: "Write new recipes", run: () => actions.onRetry?.() });
  }
  const setting = d.code ? SETTING_FIXES[d.code] : undefined;
  if (setting) buttons.push({ label: setting.label, href: setting.href });
  const fresh = buttons.filter((b) => !seen.has(b.label)); // a fix offered once
  for (const b of fresh) seen.add(b.label);
  if (fresh.length === 0) return null;
  return (
    <div className={styles.actions}>
      {fresh.map((b) =>
        b.href ? (
          <Link key={b.label} href={b.href} className="btn">
            {b.label}
          </Link>
        ) : (
          <button key={b.label} type="button" className={b.primary ? "btn btn-primary" : "btn"} disabled={busy} onClick={b.run}>
            {b.label}
          </button>
        ),
      )}
    </div>
  );
}

function Reason({ d, actions, busy, seen }: { d: PlanDiagnostic; actions: FixActions; busy: boolean; seen: Set<string> }) {
  return (
    <div className={styles.reason}>
      <p>{d.message}</p>
      <Fixes d={d} actions={actions} busy={busy} seen={seen} />
      {d.items && d.items.length > 0 && (
        <details>
          <summary>See what it would buy</summary>
          <ul className="small">
            {d.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

/** The final `result` line when it isn't a plan (M17, P4; C6 Infeasible): Pottle oops and one to three
 * reasons in plain words, each said once with its fix as a button: "Allow a $37 top-up", "Switch to
 * shopping", "Raise the budget to $55", "Allow 65 min on Monday", "Use simpler recipes", "Allow fancy
 * recipes", "Change calories", "Review held items". The items a money fix would buy sit behind "See what it
 * would buy". No command-line wording. */
export function NoPlanFits({ event, actions = {}, busy = false }: { event: PlanStreamEvent; actions?: FixActions; busy?: boolean }) {
  const problem = event.problem;
  const list = reasons(event);
  const seen = new Set<string>();
  const title = problem?.title ?? (event.status === "infeasible" ? "No plan fits" : "Planning didn't finish");
  return (
    <section className={`card ${styles.failure}`} role="alert">
      <Pottle state="oops" size={64} />
      <h2 className={styles.title}>{title}</h2>
      {list.length === 0 && problem?.detail && <p>{problem.detail}</p>}
      {list.slice(0, SHOWN).map((d, i) => (
        <Reason key={`${i}-${d.message ?? ""}`} d={d} actions={actions} busy={busy} seen={seen} />
      ))}
      {list.length > SHOWN && (
        <details>
          <summary>More reasons</summary>
          {list.slice(SHOWN).map((d, i) => (
            <Reason key={`more-${i}-${d.message ?? ""}`} d={d} actions={actions} busy={busy} seen={seen} />
          ))}
        </details>
      )}
      {(event.notes ?? []).map((n, i) => (
        <p key={`note-${i}`} className="small muted">
          {n}
        </p>
      ))}
    </section>
  );
}
