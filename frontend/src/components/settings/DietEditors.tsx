"use client";

// Diet editors (S0 Diet group): frequency caps, daily amount caps, and the ingredients you exclude or dislike.
import { useState } from "react";

import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { Segmented } from "@/components/ui/Segmented";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { Stepper } from "@/components/ui/Stepper";
import { api } from "@/lib/api/client";
import type { IngredientHit, SettingsOut, UserSettings } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";
import { CAP_MEALS, capAmount, dailyCapBounds } from "@/lib/settings/fields";

import type { Change } from "./Controls";
import styles from "./DietEditors.module.css";

/** One stepper per cap (pork as a meal component is the default one). */
export function CapsControl({ settings, onChange }: { settings: UserSettings; onChange: Change }) {
  const caps = settings.frequency_caps ?? [];
  if (caps.length === 0) return <p className="muted">No caps yet.</p>;
  return (
    <>
      {caps.map((cap, i) => (
        <Stepper
          key={cap.label}
          size="compact"
          label={cap.label}
          value={cap.max_meals_per_week}
          unit={cap.max_meals_per_week === 1 ? "meal a week" : "meals a week"}
          format={(v) => (v === 0 ? "Never" : String(v))}
          {...CAP_MEALS}
          onChange={(n) => onChange({ frequency_caps: caps.map((c, j) => (j === i ? { ...c, max_meals_per_week: n } : c)) })}
        />
      ))}
    </>
  );
}

/** Two steppers per daily cap (M16, step 2b.5): the usual amount a day and the most a day, counting every meal.
 * Plans keep to the usual amount when another plan fits, and never go over the most. */
export function DailyCapsControl({ settings, onChange }: { settings: UserSettings; onChange: Change }) {
  const caps = settings.daily_amount_caps ?? [];
  if (caps.length === 0) return <p className="muted">No daily caps.</p>;
  function set(i: number, key: "usual" | "maximum", value: number) {
    onChange({ daily_amount_caps: caps.map((c, j) => (j === i ? { ...c, [key]: value } : c)) });
  }
  return (
    <>
      {caps.map((cap, i) => {
        const bounds = dailyCapBounds(cap.unit);
        const unit = (n: number) => capAmount(n, cap.unit).replace(/^[\d.]+ ?/, "") || undefined;
        return (
          <div key={cap.ingredient} className={styles.capGroup} role="group" aria-label={cap.label}>
            <p className={styles.capTitle}>{cap.label}</p>
            <Stepper
              size="compact"
              label={`${cap.label} usually`}
              value={cap.usual}
              unit={unit(cap.usual) ? `${unit(cap.usual)} a day` : "a day"}
              decimal={bounds.step < 1}
              {...bounds}
              onChange={(n) => set(i, "usual", n)}
            />
            <Stepper
              size="compact"
              label={`${cap.label} at most`}
              value={cap.maximum}
              unit={unit(cap.maximum) ? `${unit(cap.maximum)} a day` : "a day"}
              decimal={bounds.step < 1}
              {...bounds}
              min={bounds.step}
              onChange={(n) => set(i, "maximum", n)}
            />
          </div>
        );
      })}
    </>
  );
}

type Kind = "exclude" | "dislike";
const KINDS: { value: Kind; label: string }[] = [
  { value: "exclude", label: "Never use" },
  { value: "dislike", label: "Use less" },
];

/** Foods I don't eat (step 2b.6, AA5): your never-use list, like beef (plans, searches and new ideas leave them
 * out), with Allow again, and what you'd rather use less. Each change is saved at once (an ingredient decision,
 * not a setting). Never use this on a recipe line adds to it too. */
export function PreferencesEditor({ onDone, online }: { onDone: () => void; online: boolean }) {
  const loaded = useApi<SettingsOut>("/api/v1/settings");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<IngredientHit[]>([]);
  const [kind, setKind] = useState<Kind>("exclude");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<unknown>(null);
  const mine = (loaded.data?.preferences ?? []).filter((p) => p.preference === "exclude" || p.preference === "dislike");

  async function search(value: string) {
    setQuery(value);
    if (value.trim().length < 2) {
      setHits([]);
      return;
    }
    try {
      setHits(await api<IngredientHit[]>(`/api/v1/ingredients?q=${encodeURIComponent(value.trim())}&limit=6`));
    } catch (e) {
      setProblem(e);
    }
  }

  async function set(ingredientId: number, preference: Kind | null) {
    setBusy(true);
    setProblem(null);
    try {
      const url = `/api/v1/settings/ingredient-preferences/${ingredientId}`;
      if (preference) loaded.setData(await api<SettingsOut>(url, { method: "PUT", json: { preference, reason: "set in Settings" } }));
      else {
        await api(url, { method: "DELETE" });
        await loaded.reload();
      }
      setQuery("");
      setHits([]);
    } catch (e) {
      setProblem(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <QuestionScreen
      title="Foods I don't eat"
      why="Plans, searches and new ideas never use these, like beef. Use less lets one in only when nothing else fits."
      onBack={onDone}
      primaryLabel="Done"
      onPrimary={onDone}
    >
      {!loaded.data ? (
        loaded.error ? <ErrorState error={loaded.error} onRetry={() => void loaded.reload()} /> : <Skeleton cards={1} />
      ) : (
        <>
          <ul className="list">
            <li className={styles.row}>
              <span>
                <strong>Beef</strong> <span className="badge">Always</span>
                <span className="small muted"> Includes broth, tallow and gelatin from beef.</span>
              </span>
            </li>
            {mine.map((p) => (
              <li key={p.ingredient_id} className={styles.row}>
                <span>
                  <strong>{p.name}</strong> <span className="badge">{p.preference === "exclude" ? "Never use" : "Use less"}</span>
                </span>
                <button type="button" className="btn btn-small" disabled={busy || !online} onClick={() => void set(p.ingredient_id, null)} aria-label={`${p.preference === "exclude" ? "Allow again" : "Remove"}: ${p.name}`}>
                  {p.preference === "exclude" ? "Allow again" : "Remove"}
                </button>
              </li>
            ))}
          </ul>
          <h2 className={styles.add}>Add one</h2>
          <Segmented label="Kind" options={KINDS} value={kind} onChange={setKind} />
          <label htmlFor="pref-search" className="sr-only">
            Ingredient
          </label>
          <input id="pref-search" placeholder="Search: cilantro, mushrooms…" value={query} disabled={!online} onChange={(e) => void search(e.target.value)} />
          <ul className="list">
            {hits.map((hit) => (
              <li key={hit.id}>
                <button
                  type="button"
                  className={`btn btn-block ${styles.hit}`}
                  disabled={busy || hit.status === "excluded"}
                  onClick={() => void set(hit.id, kind)}
                >
                  {hit.name}
                  {hit.status !== "allowed" && <span className="badge">{hit.status}</span>}
                </button>
              </li>
            ))}
          </ul>
          {!online && <p className="small muted">Needs a connection.</p>}
        </>
      )}
      {problem !== null && <ErrorState error={problem} title="Couldn't change that" />}
    </QuestionScreen>
  );
}
