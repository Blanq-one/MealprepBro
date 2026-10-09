"use client";

import { useEffect, useState } from "react";

import type { PlanStreamEvent } from "@/lib/api/types";

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

/** The final `result` line when it isn't a plan: the problem and each diagnostic, plus any notes. */
export function PlanFailure({ event }: { event: PlanStreamEvent }) {
  const problem = event.problem;
  const diagnostics = (problem?.diagnostics ?? []) as { message?: string }[];
  return (
    <section className="notice notice-danger" role="alert">
      <strong>{problem?.title ?? (event.status === "infeasible" ? "No plan fits this week" : "Planning failed")}</strong>
      {problem?.detail && <p>{problem.detail}</p>}
      {diagnostics.length > 0 && (
        <ul>
          {diagnostics.map((d, i) => (
            <li key={`${i}-${d.message ?? ""}`}>{d.message}</li>
          ))}
        </ul>
      )}
      {(event.notes ?? []).map((n, i) => (
        <p key={`note-${i}`} className="small">
          {n}
        </p>
      ))}
    </section>
  );
}
