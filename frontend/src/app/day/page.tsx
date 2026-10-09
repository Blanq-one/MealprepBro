"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { MarkCooked } from "@/components/MarkCooked";
import { Page } from "@/components/Page";
import { ProblemNotice, Spinner, SyncNote } from "@/components/Status";
import type { PlanSummary } from "@/lib/api/types";
import { dayLabel } from "@/lib/format/dates";
import { grouped, minutesLabel, slotLabel } from "@/lib/format/labels";
import { useApi } from "@/lib/hooks/useApi";

import styles from "./day.module.css";

function DayView() {
  const params = useSearchParams();
  const planId = params.get("plan");
  const date = params.get("date");
  const plan = useApi<PlanSummary>(planId ? `/api/v1/plans/${planId}` : null);
  if (!planId || !date) return <p>Open a day from the week view.</p>;
  if (plan.loading) return <Spinner />;
  if (plan.error || !plan.data) return <ProblemNotice error={plan.error} />;
  const day = plan.data.days.find((d) => d.day === date);
  if (!day) return <p>That day isn&apos;t in this plan.</p>;
  const sessions = plan.data.batches.filter((b) => b.cook_on === date);
  const index = plan.data.days.indexOf(day);
  const prev = plan.data.days[index - 1];
  const next = plan.data.days[index + 1];

  return (
    <>
      <div className="row-between">
        {prev ? (
          <Link className="btn btn-small" href={`/day/?plan=${planId}&date=${prev.day}`} aria-label="Previous day">
            ‹
          </Link>
        ) : (
          <span />
        )}
        <h1>{dayLabel(day.day)}</h1>
        {next ? (
          <Link className="btn btn-small" href={`/day/?plan=${planId}&date=${next.day}`} aria-label="Next day">
            ›
          </Link>
        ) : (
          <span />
        )}
      </div>
      <p className="muted">
        {grouped(day.kcal)} / {grouped(day.kcal_target)} kcal · {day.protein_g} g protein
      </p>
      <SyncNote syncedAt={plan.syncedAt} fromCache={plan.fromCache} />
      {!day.is_cook_day && <p className="notice">Leftovers day: no cooking, everything is already made.</p>}

      <h2>Meals</h2>
      <div className={styles.carousel} aria-label="Meals (swipe)">
        {day.meals.map((meal) => (
          <Link key={`${meal.slot}-${meal.cook_batch_id}`} href={`/recipe/?batch=${meal.cook_batch_id}`} className={`card ${styles.slide}`}>
            <span className="muted small">{slotLabel(meal.slot)}</span>
            <strong className={styles.slideTitle}>{meal.title}</strong>
            <span>{meal.kcal} kcal · {meal.protein_g} g protein</span>
            {meal.note && <span className="small muted">{meal.note}</span>}
          </Link>
        ))}
      </div>

      {day.is_cook_day && (
        <>
          <h2>Cook today</h2>
          <p className="muted small">
            {minutesLabel(day.hands_on_minutes)} hands-on, about {minutesLabel(day.elapsed_minutes)} start to finish
            {day.chill_minutes ? `, plus ${minutesLabel(day.chill_minutes)} in the fridge` : ""}
          </p>
          {sessions.map((batch) => (
            <section key={batch.id} className="card">
              <div className="row-between">
                <Link href={`/recipe/?batch=${batch.id}`}>
                  <strong>{batch.title}</strong>
                </Link>
                <span className="muted small">{batch.portions} portions</span>
              </div>
              {batch.portions_to_freeze > 0 && <p className="small">Freeze {batch.portions_to_freeze} of them.</p>}
              <MarkCooked batchId={batch.id} status={batch.status ?? "planned"} />
            </section>
          ))}
        </>
      )}
    </>
  );
}

export default function DayPage() {
  return (
    <Page>
      <DayView />
    </Page>
  );
}
