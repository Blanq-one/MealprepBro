"use client";

import Link from "next/link";

import { Emoji } from "@/components/ui/Emoji";
import { Skeleton } from "@/components/ui/States";
import type { PlanListItem, PlanSummary } from "@/lib/api/types";
import { todayIso, weekdayName } from "@/lib/format/dates";
import { dishIcon } from "@/lib/format/icons";
import { minutesLabel, slotLabel } from "@/lib/format/labels";
import { useApi } from "@/lib/hooks/useApi";

import styles from "./TodayCard.module.css";

/** Where today sits in a plan: its day, or whether the plan starts later or has ended. Date strings
 * ("YYYY-MM-DD") compare in calendar order. */
export function todayInPlan(plan: PlanSummary, today: string): { kind: "today"; index: number } | { kind: "later" | "ended"; day: string } | null {
  const index = plan.days.findIndex((d) => d.day === today);
  if (index >= 0) return { kind: "today", index };
  const first = plan.days[0];
  const last = plan.days[plan.days.length - 1];
  if (first && today < first.day) return { kind: "later", day: first.day };
  if (last && today > last.day) return { kind: "ended", day: last.day };
  return null;
}

export function TodayView({ plan, today }: { plan: PlanSummary; today: string }) {
  const where = todayInPlan(plan, today);
  if (!where) return null;
  if (where.kind !== "today") {
    return (
      <section className={`card ${styles.card}`} aria-label="Today">
        <h2 className={styles.heading}>Today</h2>
        <p>{where.kind === "later" ? `Your plan starts ${weekdayName(where.day)}.` : `Your plan ended ${weekdayName(where.day)}.`}</p>
        <Link href={`/plan/?id=${plan.id}`} className="btn btn-block">
          Open your plan
        </Link>
      </section>
    );
  }
  const day = plan.days[where.index];
  if (!day) return null;
  return (
    <section className={`card ${styles.card}`} aria-label="Today">
      <Link href={`/day/?plan=${plan.id}&date=${day.day}`} className={styles.link}>
        <h2 className={styles.heading}>Today</h2>
        <ul className="list">
          {day.meals.map((meal) => {
            const icon = dishIcon(meal.dish_category);
            return (
              <li key={`${meal.slot}-${meal.cook_batch_id}`} className={styles.meal}>
                <Emoji symbol={icon.emoji} label={icon.label} className={styles.icon} />
                <span>
                  <span className={styles.slot}>{slotLabel(meal.slot)}</span>
                  <span className={styles.title}>{meal.title}</span>
                </span>
              </li>
            );
          })}
        </ul>
        <p className={styles.cook}>
          {day.cook_note}
          {day.hands_on_minutes > 0 ? ` · ${minutesLabel(day.hands_on_minutes)} hands-on` : ""}
        </p>
      </Link>
      <Link href={`/plan/?id=${plan.id}`} className="btn btn-block">
        Open your plan
      </Link>
    </section>
  );
}

/** The Cook home Today card (C0 item 4): today's meals from your current plan and what to cook today. */
export function TodayCard() {
  const plans = useApi<PlanListItem[]>("/api/v1/plans?limit=10");
  const current = plans.data?.find((p) => p.is_current) ?? null;
  const plan = useApi<PlanSummary>(current ? `/api/v1/plans/${current.id}` : null);

  if (plans.loading || plan.loading) return <Skeleton cards={1} label="Loading today" />;
  if ((plans.error && !plans.data) || (plan.error && !plan.data)) {
    return (
      <section className="card" aria-label="Today">
        <p>Couldn&apos;t load today&apos;s meals.</p>
        <button
          type="button"
          className="btn btn-block"
          onClick={() => void (plans.error ? plans.reload() : plan.reload())}
        >
          Try again
        </button>
      </section>
    );
  }
  if (!plan.data) {
    return (
      <section className="card" aria-label="Today">
        <h2 className={styles.heading}>Today</h2>
        <p className="muted">No current plan yet.</p>
        <Link href="/plan/new/" className="btn btn-primary btn-block">
          Plan a week
        </Link>
      </section>
    );
  }
  return <TodayView plan={plan.data} today={todayIso()} />;
}
