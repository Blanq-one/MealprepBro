"use client";

import Link from "next/link";
import { useState } from "react";

import { MarkCooked } from "@/components/MarkCooked";
import { NeedsConnection } from "@/components/ui/States";
import type { BatchDetail, Step } from "@/lib/api/types";
import { useWakeLock } from "@/lib/cook/wakeLock";
import { humanize } from "@/lib/format/labels";

import styles from "./CookingMode.module.css";

type Screen = { kind: "ingredients" } | { kind: "step"; step: Step; number: number } | { kind: "done" };

/** Ingredients first, then each step, then Mark cooked. */
export function cookingScreens(steps: readonly Step[]): Screen[] {
  return [{ kind: "ingredients" }, ...steps.map((step, i) => ({ kind: "step" as const, step, number: i + 1 })), { kind: "done" }];
}

/** Cooking mode (C8): large, one step at a time, back and next, safety lines highlighted, the screen kept
 * awake, and Mark cooked at the end. Every line is the recipe page's. */
export function CookingMode({ batch, online, onCooked }: { batch: BatchDetail; online: boolean; onCooked?: () => void }) {
  const [index, setIndex] = useState(0);
  const awake = useWakeLock(true);
  const screens = cookingScreens(batch.recipe.steps);
  const screen = screens[index] ?? screens[0];
  const steps = batch.recipe.steps.length;
  const notes = new Map((batch.pantry_notes ?? []).map((n) => [n.ingredient_id, n.note]));
  const last = index === screens.length - 1;

  return (
    <div className={styles.mode}>
      <header className={styles.top}>
        <Link href={`/recipe/?batch=${batch.id}`} className={styles.close} aria-label="Leave cooking mode">
          ✕
        </Link>
        <span className={styles.progress} aria-live="polite">
          {screen?.kind === "step" ? `Step ${screen.number} of ${steps}` : screen?.kind === "done" ? "Done" : "Get ready"}
        </span>
        <span className={styles.awake}>{awake === "on" ? "Screen stays on" : ""}</span>
      </header>
      <h1 className={styles.title}>{batch.recipe.title}</h1>

      <section className={styles.body} aria-label={screen?.kind === "step" ? `Step ${screen.number}` : screen?.kind === "done" ? "Done" : "Ingredients"}>
        {screen?.kind === "ingredients" && (
          <>
            <h2>You&apos;ll need</h2>
            <ul className={styles.ingredients}>
              {batch.lines.map((line, i) => (
                <li key={`${line.ingredient_id}-${i}`}>
                  <strong>{line.display}</strong> {line.name}
                  {line.preparation ? `, ${line.preparation}` : ""}
                  {notes.get(line.ingredient_id) && <span className={styles.note}>{notes.get(line.ingredient_id)}</span>}
                </li>
              ))}
            </ul>
          </>
        )}
        {screen?.kind === "step" && (
          <>
            <p className={styles.section}>{humanize(screen.step.section)}</p>
            <p className={styles.stepText}>{screen.step.text}</p>
            {(screen.step.appliance_temp_f || screen.step.duration_minutes) && (
              <p className={styles.meta}>
                {screen.step.appliance_temp_f ? `${screen.step.appliance_temp_f}°F` : ""}
                {screen.step.appliance_temp_f && screen.step.duration_minutes ? " · " : ""}
                {screen.step.duration_minutes ? `${screen.step.duration_minutes} min` : ""}
              </p>
            )}
            {screen.step.safety_note && (
              <p className="notice notice-safety" data-testid="safety-note">
                <strong>Food safety:</strong> {screen.step.safety_note}
              </p>
            )}
          </>
        )}
        {screen?.kind === "done" && (
          <>
            <h2>All done?</h2>
            <p>Mark it cooked to take what you used out of your pantry.</p>
            <MarkCooked batchId={batch.id} status={batch.status} onCooked={onCooked} disabled={!online} />
            {!online && <NeedsConnection />}
          </>
        )}
      </section>

      <nav className={styles.nav} aria-label="Steps">
        <button type="button" className={`btn ${styles.navButton}`} onClick={() => setIndex(Math.max(0, index - 1))} disabled={index === 0}>
          Back
        </button>
        {!last && (
          <button type="button" className={`btn btn-primary ${styles.navButton}`} onClick={() => setIndex(Math.min(screens.length - 1, index + 1))}>
            {index === 0 ? "Start" : "Next"}
          </button>
        )}
      </nav>
    </div>
  );
}
