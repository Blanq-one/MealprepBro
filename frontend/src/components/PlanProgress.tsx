"use client";

import { useEffect, useState } from "react";

import type { PlanStreamEvent } from "@/lib/api/types";
import { weekdayName } from "@/lib/format/dates";
import { formatCents } from "@/lib/format/money";

import { Spinner } from "./Status";
import styles from "./PlanProgress.module.css";

/** Spinner, the latest stage message and the seconds since the request started. */
export function PlanProgress({ startedAt, event }: { startedAt: number; event: PlanStreamEvent | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.round((now - startedAt) / 1000));
  return (
    <section className={`card ${styles.progress}`} aria-live="polite">
      <Spinner label={event?.message ?? "Starting"} />
      <p className="muted small">
        {seconds} s · usually under a minute; writing new recipes can take two or three.
      </p>
    </section>
  );
}

/** One problem diagnostic as the server sends it (planning/orchestrator.problem_json). */
type PlanDiagnostic = {
  code?: string;
  message?: string;
  suggested_cents?: number;
  items?: string[];
  day?: string; // "YYYY-MM-DD"
  suggested_minutes?: number; // COOK_TIME_SHORT: the minutes that day needs (P4)
  mood?: string; // RECIPES_LEFT_OUT: the mood the left-out recipes need, e.g. "fancy"
};

/** "$37" for a whole-dollar suggestion (formatting only: the server rounded it up). */
function dollars(cents: number): string {
  return formatCents(cents).replace(/\.00$/, "");
}

export type FailureActions = {
  /** Plan again from what you have, allowing this top-up. */
  onTopUp?: (cents: number) => void;
  /** Plan again in shopping mode. */
  onShop?: () => void;
  /** Plan again with this budget. */
  onBudget?: (cents: number) => void;
  /** Plan again allowing this many hands-on minutes on that day (P4). */
  onMinutes?: (day: string, minutes: number) => void;
  /** Plan again with this mood on that day ("simple" = simpler recipes), or on every day when day is null. */
  onMood?: (day: string | null, mood: string) => void;
};

/** The final `result` line when it isn't a plan (2b.4 approval, B): each problem once, in plain words, with buttons
 * for the money fixes ("Allow a $37 top-up", "Switch to shopping", "Raise the budget to $55") and what the fix
 * would buy behind "See what it would buy"; for time and mood (P4), "Allow 50 min on Monday", "Use simpler
 * recipes" and "Allow fancy recipes". */
export function PlanFailure({ event, actions = {}, busy = false }: { event: PlanStreamEvent; actions?: FailureActions; busy?: boolean }) {
  const problem = event.problem;
  const all = (problem?.diagnostics ?? []) as PlanDiagnostic[];
  const diagnostics = all.filter((d, i) => all.findIndex((o) => o.message === d.message) === i); // never twice
  return (
    <section className="notice notice-danger" role="alert">
      <strong>{problem?.title ?? (event.status === "infeasible" ? "No plan fits this week" : "Planning failed")}</strong>
      {diagnostics.length === 0 && problem?.detail && <p>{problem.detail}</p>}
      {diagnostics.map((d, i) => (
        <div key={`${i}-${d.message ?? ""}`} className={styles.diagnostic}>
          <p>{d.message}</p>
          {d.code === "INVENTORY_SHORT" && d.suggested_cents && (
            <div className={styles.actions}>
              {actions.onTopUp && (
                <button type="button" className="btn btn-primary" disabled={busy} onClick={() => actions.onTopUp?.(d.suggested_cents ?? 0)}>
                  Allow a {dollars(d.suggested_cents)} top-up
                </button>
              )}
              {actions.onShop && (
                <button type="button" className="btn" disabled={busy} onClick={() => actions.onShop?.()}>
                  Switch to shopping
                </button>
              )}
            </div>
          )}
          {d.code === "COOK_TIME_SHORT" && d.day && d.suggested_minutes && (
            <div className={styles.actions}>
              {actions.onMinutes && (
                <button type="button" className="btn btn-primary" disabled={busy} onClick={() => actions.onMinutes?.(d.day ?? "", d.suggested_minutes ?? 0)}>
                  Allow {d.suggested_minutes} min on {weekdayName(d.day)}
                </button>
              )}
              {actions.onMood && (
                <button type="button" className="btn" disabled={busy} onClick={() => actions.onMood?.(d.day ?? null, "simple")}>
                  Use simpler recipes
                </button>
              )}
            </div>
          )}
          {d.code === "RECIPES_LEFT_OUT" && d.mood && actions.onMood && (
            <div className={styles.actions}>
              <button type="button" className="btn" disabled={busy} onClick={() => actions.onMood?.(null, d.mood ?? "")}>
                Allow {d.mood} recipes
              </button>
            </div>
          )}
          {d.code === "BUDGET_SHORT" && d.suggested_cents && actions.onBudget && (
            <div className={styles.actions}>
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => actions.onBudget?.(d.suggested_cents ?? 0)}>
                Raise the budget to {dollars(d.suggested_cents)}
              </button>
            </div>
          )}
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
      ))}
      {(event.notes ?? []).map((n, i) => (
        <p key={`note-${i}`} className="small">
          {n}
        </p>
      ))}
    </section>
  );
}
