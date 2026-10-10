import type { ReactNode } from "react";

import type { RecipeVersion, Step } from "@/lib/api/types";
import { dishIcon } from "@/lib/format/icons";
import { minutesLabel } from "@/lib/format/labels";
import { formatCents } from "@/lib/format/money";

import { Emoji } from "./ui/Emoji";

import styles from "./RecipeView.module.css";

export type RecipeLine = {
  key: string;
  name: string;
  display: string;
  preparation: string | null;
  optional: boolean;
  note?: string | null;
  /** A longer line under it: what it uses of what you have, or a substitute (server text). */
  detail?: string | null;
};

const SECTION_LABELS: Record<string, string> = {
  prep: "Prep",
  marinate: "Marinate",
  stovetop: "Stovetop",
  oven: "Oven",
  air_fryer: "Air fryer",
  rice: "Rice",
  microwave: "Microwave",
  no_cook: "No-cook",
  assembly: "Assemble",
  portioning: "Portion",
  storage: "Storage",
  reheating: "Reheating",
};

function sections(steps: Step[]): [string, Step[]][] {
  const out: [string, Step[]][] = [];
  for (const step of steps) {
    const last = out[out.length - 1];
    if (last && last[0] === step.section) last[1].push(step);
    else out.push([step.section, [step]]);
  }
  return out;
}

function sectionLabel(section: string): string {
  return SECTION_LABELS[section] ?? section.replace(/_/g, " ");
}

/** A recipe as the cook reads it: large type, sections in order, the app's safety lines highlighted. */
export function RecipeView({
  recipe,
  lines,
  notes = [],
  portionsLine,
  children,
}: {
  recipe: RecipeVersion;
  lines?: RecipeLine[];
  notes?: string[];
  /** The API's portions line ("for 2 people") in place of the recipe's portions count. */
  portionsLine?: string | null;
  children?: ReactNode;
}) {
  const shown: RecipeLine[] =
    lines ??
    recipe.lines.map((l, i) => ({
      key: `${l.ingredient_id}-${i}`,
      name: l.name,
      display: l.display,
      preparation: l.preparation,
      optional: l.optional,
    }));
  const nutrition = recipe.per_portion;
  const heme = nutrition.heme_iron;
  const icon = dishIcon(recipe.dish_category);
  return (
    <article className={styles.recipe}>
      <header>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <Emoji symbol={icon.emoji} label={icon.label} className={styles.icon} />
          <h1>{recipe.title}</h1>
          {recipe.badge === "draft" && <span className="badge badge-warn">Draft: adjust me</span>}
          {recipe.is_favorite && <span className="badge badge-accent">Favorite</span>}
          {recipe.is_saved && <span className="badge badge-accent">Saved</span>}
        </div>
        {recipe.description && <p className="muted">{recipe.description}</p>}
        <p className="small muted">
          {portionsLine ?? `${recipe.portions} portions`} ({recipe.portion_size.replace(/_/g, " ")}) · {minutesLabel(recipe.active_minutes)}{" "}
          hands-on, {minutesLabel(recipe.total_minutes)} total{recipe.time_note ? ` (${recipe.time_note})` : ""}
        </p>
        {recipe.labels.length > 0 && (
          <p className="row" style={{ flexWrap: "wrap" }}>
            {recipe.labels.map((label) => (
              <span key={label} className="badge badge-accent">
                {label}
              </span>
            ))}
          </p>
        )}
      </header>

      {notes.map((note) => (
        <p key={note} className="notice">
          {note}
        </p>
      ))}

      {children}

      <section className="card" aria-labelledby="ingredients-h">
        <h2 id="ingredients-h">Ingredients</h2>
        <ul className={`list ${styles.lines}`}>
          {shown.map((line) => (
            <li key={line.key}>
              <span className={styles.amount}>{line.display}</span>{" "}
              <span>
                {line.name}
                {line.preparation ? `, ${line.preparation}` : ""}
                {line.optional && <span className="muted"> (optional)</span>}
              </span>
              {line.note && <span className="badge"> {line.note}</span>}
              {line.detail && <span className={styles.detail}>{line.detail}</span>}
            </li>
          ))}
        </ul>
        {recipe.per_container && <p className="small muted">{recipe.per_container}</p>}
      </section>

      {sections(recipe.steps).map(([section, steps], i) => (
        <section key={`${section}-${i}`} className="card" aria-label={sectionLabel(section)}>
          <h2>{sectionLabel(section)}</h2>
          <ol className={styles.steps}>
            {steps.map((step, j) => (
              <li key={`${section}-${i}-${j}`}>
                <p>{step.text}</p>
                {(step.appliance_temp_f || step.duration_minutes) && (
                  <p className="small muted">
                    {step.appliance_temp_f ? `${step.appliance_temp_f}°F` : ""}
                    {step.appliance_temp_f && step.duration_minutes ? " · " : ""}
                    {step.duration_minutes ? `${step.duration_minutes} min` : ""}
                  </p>
                )}
                {step.safety_note && (
                  <p className="notice notice-safety" data-testid="safety-note">
                    <strong>Food safety:</strong> {step.safety_note}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </section>
      ))}

      <section className="card" aria-labelledby="nutrition-h">
        <h2 id="nutrition-h">Per portion</h2>
        <p>
          <strong>{nutrition.kcal} kcal</strong>
        </p>
        <ul className={`list ${styles.nutrients}`}>
          {nutrition.nutrients.map((n) => (
            <li key={n.code}>
              <span>{n.display_name}</span>
              <span>
                {n.amount} {n.unit}
                {n.label && <span className="badge badge-accent"> {n.label}</span>}
                {!n.complete && <span className="muted small"> (incomplete)</span>}
              </span>
            </li>
          ))}
        </ul>
        {heme && (
          <p className="small" data-testid="heme">
            Iron, estimated split: {heme.heme_mg} mg heme · {heme.non_heme_mg} mg non-heme (estimated)
          </p>
        )}
        {recipe.heme_note && <p className="small muted">{recipe.heme_note}</p>}
        {recipe.incomplete_reasons.length > 0 && (
          <p className="small muted">Incomplete: {recipe.incomplete_reasons.join("; ")}</p>
        )}
      </section>

      {recipe.costs.length > 0 && (
        <section className="card" aria-labelledby="cost-h">
          <h2 id="cost-h">Cost per portion</h2>
          <ul className="list">
            {recipe.costs.map((c) => (
              <li key={c.store_id} className="row-between">
                <span>{c.store_name}</span>
                <span>
                  {formatCents(c.per_portion_cents)}
                  {c.uses_estimates ? " est." : ""}
                  {!c.complete && <span className="muted small"> + unpriced items</span>}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
