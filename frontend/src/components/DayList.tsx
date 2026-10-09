import Link from "next/link";

import type { PlanSummary } from "@/lib/api/types";
import { dayLabel } from "@/lib/format/dates";
import { grouped, minutesLabel, slotLabel } from "@/lib/format/labels";

import styles from "./DayList.module.css";

export function DayList({ plan }: { plan: PlanSummary }) {
  return (
    <ol className={`list ${styles.days}`} aria-label="Days">
      {plan.days.map((day) => (
        <li key={day.day} className="card">
          <div className="row-between">
            <Link href={`/day/?plan=${plan.id}&date=${day.day}`} className={styles.dayLink}>
              {dayLabel(day.day)}
            </Link>
            <span className="muted small">
              {grouped(day.kcal)} kcal · {day.protein_g} g protein
            </span>
          </div>
          <p className="small muted">
            {day.is_cook_day ? (
              <>Cook day · {minutesLabel(day.hands_on_minutes)} hands-on</>
            ) : (
              <span className="badge badge-accent">Leftovers day</span>
            )}
          </p>
          <ul className="list">
            {day.meals.map((meal) => (
              <li key={`${meal.slot}-${meal.cook_batch_id}`}>
                <Link href={`/recipe/?batch=${meal.cook_batch_id}`} className={styles.meal}>
                  <span className={styles.slot}>{slotLabel(meal.slot)}</span>
                  <span className={styles.title}>
                    {meal.title}
                    {meal.from_freezer && <span className="badge"> from freezer</span>}
                  </span>
                  <span className="muted small">{meal.kcal} kcal</span>
                </Link>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
