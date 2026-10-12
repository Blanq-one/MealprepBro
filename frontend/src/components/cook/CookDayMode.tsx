"use client";

import Link from "next/link";
import { useState } from "react";

import { MarkCooked } from "@/components/MarkCooked";
import { NeedsConnection } from "@/components/ui/States";
import type { Day, PlanSummary } from "@/lib/api/types";
import { useWakeLock } from "@/lib/cook/wakeLock";
import { dayLabel } from "@/lib/format/dates";

import styles from "./CookingMode.module.css";

/** The cook-day cooking mode (FLOW_SPEC §20.4, 2b.7): the day's batches, then its timeline one line at a time
 * across dishes (each line opens its dish's steps), then Mark cooked for each batch. The screen stays awake.
 * Every line is the timeline's, templated by the server. */
export function CookDayMode({ plan, day, online }: { plan: PlanSummary; day: Day; online: boolean }) {
  const [index, setIndex] = useState(0);
  const awake = useWakeLock(true);
  const batches = plan.batches.filter((b) => b.cook_on === day.day);
  const lines = (day.timeline ?? []).filter((l) => l.kind !== "done");
  const total = lines.length + 2; // the overview, each line, then done
  const line = index >= 1 && index <= lines.length ? lines[index - 1] : null;
  const last = index === total - 1;
  return (
    <div className={styles.mode}>
      <header className={styles.top}>
        <Link href={`/cook/plan/?id=${plan.id}&date=${day.day}`} className={styles.close} aria-label="Leave cooking mode">
          ✕
        </Link>
        <span className={styles.progress} aria-live="polite">
          {line ? `${line.at_display} · ${index} of ${lines.length}` : last ? "Done" : "Get ready"}
        </span>
        <span className={styles.awake}>{awake === "on" ? "Screen stays on" : ""}</span>
      </header>
      <h1 className={styles.title}>Cook day · {dayLabel(day.day)}</h1>

      <section className={styles.body} aria-label={line ? `At ${line.at_display}` : last ? "Done" : "Today's batches"}>
        {index === 0 && (
          <>
            <h2>Today you&apos;re cooking</h2>
            <ul className={styles.ingredients}>
              {batches.map((b) => (
                <li key={b.id}>
                  <strong>{b.title}</strong> ×{b.portions}
                  {b.uses_display && <span className={styles.note}>→ {b.uses_display}</span>}
                </li>
              ))}
            </ul>
            {day.time_display && <p className={styles.meta}>{day.time_display}</p>}
          </>
        )}
        {line && (
          <>
            <p className={styles.section}>{line.at_display}</p>
            <p className={styles.stepText}>{line.text}</p>
            {line.dish && <p className={styles.meta}>{line.dish}</p>}
            {line.cook_batch_id && (
              <Link href={`/recipe/?batch=${line.cook_batch_id}`} className="btn btn-block">
                Open the {line.dish ?? "recipe"} steps
              </Link>
            )}
          </>
        )}
        {last && (
          <>
            <h2>All done?</h2>
            <p>Mark each batch cooked to take what you used out of your pantry.</p>
            {batches.map((b) => (
              <div key={b.id} className={styles.batchDone}>
                <p>
                  <strong>{b.title}</strong>
                </p>
                <MarkCooked batchId={b.id} status={b.status ?? "planned"} disabled={!online} />
              </div>
            ))}
            {!online && <NeedsConnection />}
          </>
        )}
      </section>

      <nav className={styles.nav} aria-label="Timeline">
        <button type="button" className={`btn ${styles.navButton}`} onClick={() => setIndex(Math.max(0, index - 1))} disabled={index === 0}>
          Back
        </button>
        {!last && (
          <button type="button" className={`btn btn-primary ${styles.navButton}`} onClick={() => setIndex(Math.min(total - 1, index + 1))}>
            {index === 0 ? "Start" : "Next"}
          </button>
        )}
      </nav>
    </div>
  );
}
