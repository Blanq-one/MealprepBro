"use client";

import { useEffect, useState } from "react";

import styles from "./BuildingSteps.module.css";
import { Pottle } from "./Pottle";

export type StageState = "done" | "current" | "pending";
export type Stage = { key: string; label: string; state: StageState; note?: string | null };

/** "0:23" from seconds. */
export function clockLabel(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Counts down from the server's wait (wait_s / retry_after_s) to zero. Only a timer. */
export function useCountdown(seconds: number | null, startedAt: number | null): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (seconds === null) return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [seconds, startedAt]);
  if (seconds === null || startedAt === null) return null;
  return Math.max(0, seconds - (now - startedAt) / 1000);
}

const MARKS: Record<StageState, string> = { done: "✓", current: "◌", pending: "○" };

/** The real stages from the stream (FLOW_SPEC §5.4). The list only moves when the server reports a stage; a
 * rate-limit wait is a normal step with a countdown, never an error. */
export function BuildingSteps({
  stages,
  waitS = null,
  waitStartedAt = null,
  elapsedS = null,
  onStop,
}: {
  stages: readonly Stage[];
  waitS?: number | null;
  waitStartedAt?: number | null;
  elapsedS?: number | null;
  onStop?: () => void;
}) {
  const left = useCountdown(waitS, waitStartedAt);
  return (
    <section className={styles.building} aria-label="Progress">
      <div className={styles.pottle}>
        <Pottle state="working" size={88} />
      </div>
      <ol className={styles.stages}>
        {stages.map((stage) => (
          <li key={stage.key} className={`${styles.stage} ${styles[stage.state]}`} aria-current={stage.state === "current" ? "step" : undefined}>
            <span className={styles.mark} aria-hidden="true">
              {MARKS[stage.state]}
            </span>
            <span>
              {stage.label}
              {stage.state === "current" ? "…" : ""}
              <span className="sr-only">{stage.state === "done" ? " (done)" : stage.state === "pending" ? " (next)" : " (now)"}</span>
              {stage.note && <span className={styles.note}>{stage.note}</span>}
            </span>
          </li>
        ))}
      </ol>
      {left !== null && left > 0 && (
        <p className={styles.wait} role="status">
          The recipe service needs a short breather. Back in {clockLabel(left)}
        </p>
      )}
      {elapsedS !== null && <p className={styles.elapsed}>{clockLabel(elapsedS)} elapsed</p>}
      {onStop && (
        <button type="button" className="btn btn-link btn-block" onClick={onStop}>
          Stop watching
        </button>
      )}
    </section>
  );
}
