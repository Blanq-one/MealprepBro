import Link from "next/link";

import { Emoji } from "@/components/ui/Emoji";
import type { TodayOut } from "@/lib/api/types";
import { dishIcon } from "@/lib/format/icons";
import { slotLabel } from "@/lib/format/labels";

import styles from "./TodayCard.module.css";

/** The Cook home Today card (C0 item 4), from GET /cook/home: today's meals from your current plan and what to
 * cook today, or when the plan starts or ended. Every line is the server's. */
export function TodayCard({ today }: { today: TodayOut }) {
  const planHref = `/plan/?id=${today.plan_id}`;
  if (today.state !== "today" || !today.day) {
    return (
      <section className={`card ${styles.card}`} aria-label="Today">
        <h2 className={styles.heading}>Today</h2>
        {today.message && <p>{today.message}.</p>}
        <Link href={planHref} className="btn btn-block">
          Open your plan
        </Link>
      </section>
    );
  }
  return (
    <section className={`card ${styles.card}`} aria-label="Today">
      <Link href={`/day/?plan=${today.plan_id}&date=${today.day}`} className={styles.link}>
        <h2 className={styles.heading}>Today</h2>
        <ul className="list">
          {today.meals.map((meal) => {
            const icon = dishIcon(meal.dish_category);
            return (
              <li key={`${meal.slot}-${meal.cook_batch_id}`} className={styles.meal}>
                <Emoji symbol={icon.emoji} label={icon.label} className={styles.icon} />
                <span>
                  <span className={styles.slot}>{slotLabel(meal.slot)}</span>
                  <span className={styles.title}>{meal.title}</span>
                  {meal.from_freezer && <span className="small muted"> · from the freezer</span>}
                </span>
              </li>
            );
          })}
        </ul>
        {today.cook_note && (
          <p className={styles.cook}>
            {today.cook_note}
            {today.hands_on_display ? ` · ${today.hands_on_display}` : ""}
          </p>
        )}
      </Link>
      <Link href={planHref} className="btn btn-block">
        Open your plan
      </Link>
    </section>
  );
}
