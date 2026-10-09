import type { PlanSummary } from "@/lib/api/types";
import { shortDate } from "@/lib/format/dates";
import { focusLabel, grouped, minutesLabel } from "@/lib/format/labels";
import { formatCents } from "@/lib/format/money";

import styles from "./WeekSummary.module.css";

type Warning = { code?: string; message?: string };

function limitLine(plan: PlanSummary): string | null {
  if (plan.planning_mode === "inventory") {
    return plan.purchase_limit_cents ? `Top-up ${formatCents(plan.purchase_limit_cents)}` : "Cook from what you have";
  }
  return plan.purchase_limit_cents !== null && plan.purchase_limit_cents !== undefined
    ? `Budget ${formatCents(plan.purchase_limit_cents)}`
    : null;
}

/** PRD §25: the week at a glance. Every number is the server's. */
export function WeekSummary({ plan }: { plan: PlanSummary }) {
  const limit = limitLine(plan);
  const focus = [focusLabel(plan.nutrition_focus), focusLabel(plan.secondary_focus)].filter(Boolean).join(" + ");
  return (
    <section className={`card ${styles.summary}`} aria-label="Week summary">
      <div className="row-between">
        <h1>Week of {shortDate(plan.week_start)}</h1>
        <span className={plan.status === "active" ? "badge badge-accent" : "badge"}>{plan.status}</span>
      </div>
      <dl className={styles.grid}>
        <dt>Calories</dt>
        <dd>
          {grouped(plan.kcal_planned_week)} / {grouped(plan.kcal_target_week)} kcal
        </dd>
        <dt>Nutrition focus</dt>
        <dd>{focus}</dd>
        <dt>Protein</dt>
        <dd>
          ~{plan.protein_g_per_day} g/day (target {plan.protein_target_g_per_day} g)
        </dd>
        {limit && (
          <>
            <dt>{plan.planning_mode === "inventory" ? "Mode" : "Budget"}</dt>
            <dd>{limit}</dd>
          </>
        )}
        <dt>Cash this trip</dt>
        <dd>
          {plan.costs.cash_display}
          {!plan.costs.complete && <span className="muted small"> + unpriced items</span>}
        </dd>
        <dt>Food eaten</dt>
        <dd>{plan.costs.eaten_display}</dd>
        <dt>Expected waste</dt>
        <dd>{plan.costs.expected_waste_display}</dd>
        <dt>Cooking time</dt>
        <dd>~{minutesLabel(plan.cooking_minutes_total)} hands-on</dd>
        <dt>Meals</dt>
        <dd>{plan.meals_count}</dd>
      </dl>
      {plan.cost_note && <p className="muted small">{plan.cost_note}</p>}
      {plan.store_totals.length > 1 && (
        <p className="muted small">{plan.store_totals.map((s) => `${s.store_name} ${s.display}`).join(" · ")}</p>
      )}
    </section>
  );
}

export function PlanNotices({ plan }: { plan: PlanSummary }) {
  const warnings = plan.warnings as Warning[];
  if (!plan.freeze.length && !warnings.length && !plan.notes.length) return null;
  return (
    <section aria-label="Notes">
      {plan.freeze.map((f) => (
        <p key={`${f.ingredient_id}-${f.freeze_on}-${f.use_on ?? ""}`} className="notice notice-safety">
          {f.message}
        </p>
      ))}
      {warnings.map((w, i) => (
        <p key={`w-${i}`} className="notice notice-warn">
          {w.message ?? w.code}
        </p>
      ))}
      {plan.notes.map((n, i) => (
        <p key={`n-${i}`} className="notice">
          {n}
        </p>
      ))}
    </section>
  );
}
