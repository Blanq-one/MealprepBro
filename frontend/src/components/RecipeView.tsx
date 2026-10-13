import Link from "next/link";
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
  /** "1 scoop per portion · 4 scoops for the batch of 4" (server text, A1). */
  portionNote?: string | null;
  /** Its recipe line (step 2b.6): the line's ⋯ opens its options. */
  lineId?: number | null;
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

function StepList({ steps, keyPrefix }: { steps: Step[]; keyPrefix: string }) {
  return (
    <>
      {sections(steps).map(([section, group], i) => (
        <section key={`${keyPrefix}-${section}-${i}`} className="card" aria-label={sectionLabel(section)}>
          <h2>{sectionLabel(section)}</h2>
          <ol className={styles.steps}>
            {group.map((step, j) => (
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
                {step.flag && (
                  <p className="notice notice-warn small" data-testid="step-flag">
                    <strong>Your version:</strong> {step.flag}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </section>
      ))}
    </>
  );
}

/** A prep item's steps by stage (FLOW_SPEC §19.10), each stage with how it keeps when prep stops there. */
function PrepStages({ recipe }: { recipe: RecipeVersion }) {
  const prep = recipe.prep;
  if (!prep) return <StepList steps={recipe.steps} keyPrefix="steps" />;
  return (
    <>
      {prep.stages.map((stage) => (
        <div key={stage.n} className={styles.stage}>
          <h2 className={styles.stageTitle}>
            Stage {stage.n} · {stage.state_display}
          </h2>
          <p className="small">{stage.storage.note}</p>
          <StepList steps={recipe.steps.filter((s) => (s.stage ?? prep.stages.length) === stage.n)} keyPrefix={`stage-${stage.n}`} />
        </div>
      ))}
      <details className="small muted">
        <summary>Storage sources</summary>
        <ul>
          {[...new Set(prep.stages.flatMap((s) => s.storage.sources))].map((source) => (
            <li key={source}>{source}</li>
          ))}
        </ul>
      </details>
    </>
  );
}

/** An assembly (FLOW_SPEC §19.10): its items, each opening its own page, and the eating-day instruction. */
function AssemblyItems({ recipe }: { recipe: RecipeVersion }) {
  const assembly = recipe.assembly;
  if (!assembly) return null;
  return (
    <>
      <section className="card" aria-labelledby="items-h">
        <h2 id="items-h">In this meal</h2>
        <ul className={`list ${styles.lines}`}>
          {assembly.items.map((item) => (
            <li key={item.recipe_id}>
              <Link href={`/recipe/?version=${item.version_id}`}>
                <span className={styles.amount}>{item.portions_display}</span> {item.title}
              </Link>
              <span className={styles.detail}>
                {item.kcal} kcal · {item.protein_g} g protein
              </span>
            </li>
          ))}
        </ul>
      </section>
      <section className="card" aria-labelledby="instruction-h">
        <h2 id="instruction-h">On the day</h2>
        <p>{assembly.instruction}</p>
      </section>
    </>
  );
}

/** A recipe as the cook reads it: large type, sections in order, the app's safety lines highlighted. */
export function RecipeView({
  recipe,
  lines,
  notes = [],
  portionsLine,
  stepsSlot,
  lineAction,
  children,
}: {
  recipe: RecipeVersion;
  lines?: RecipeLine[];
  notes?: string[];
  /** The API's portions line ("for 2 people") in place of the recipe's portions count. */
  portionsLine?: string | null;
  /** Shown in place of the steps while a new idea's steps are being written (C8). */
  stepsSlot?: ReactNode;
  /** Beside each line with a line id: its ⋯ (step 2b.6). */
  lineAction?: (line: RecipeLine) => ReactNode;
  children?: ReactNode;
}) {
  const shown: RecipeLine[] =
    lines ??
    recipe.lines.map((l, i) => ({
      key: `${l.ingredient_id}-${i}`,
      name: l.name,
      display: l.amount_display || l.display,
      preparation: l.preparation,
      optional: l.optional,
      portionNote: l.portion_note ?? null,
      lineId: l.line_id ?? null,
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
        {recipe.your_version && recipe.change_summary && (
          <p className="notice" data-testid="your-version">
            {recipe.change_summary}
          </p>
        )}
        {recipe.description && !stepsSlot && <p className="muted">{recipe.description}</p>}
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

      {recipe.kind === "assembly" && <AssemblyItems recipe={recipe} />}

      {(recipe.kind !== "assembly" || shown.length > 0) && (
      <section className="card" aria-labelledby="ingredients-h">
        <h2 id="ingredients-h">{recipe.kind === "assembly" ? "Add-ons, per portion" : "Ingredients"}</h2>
        <ul className={`list ${styles.lines}`}>
          {shown.map((line) => (
            <li key={line.key} className={lineAction && line.lineId ? styles.withMore : undefined}>
              <span className={styles.lineText}>
                <span className={styles.amount}>{line.display}</span>{" "}
                <span>
                  {line.name}
                  {line.preparation ? `, ${line.preparation}` : ""}
                  {line.optional && <span className="muted"> (optional)</span>}
                </span>
                {line.note && <span className="badge"> {line.note}</span>}
                {line.portionNote && <span className={styles.detail}>{line.portionNote}</span>}
                {line.detail && <span className={styles.detail}>{line.detail}</span>}
              </span>
              {lineAction && line.lineId ? lineAction(line) : null}
            </li>
          ))}
        </ul>
        {recipe.per_container && <p className="small muted">{recipe.per_container}</p>}
      </section>
      )}

      {stepsSlot}
      {!stepsSlot && (recipe.kind === "prep_item" ? <PrepStages recipe={recipe} /> : <StepList steps={recipe.steps} keyPrefix="steps" />)}

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
