"use client";

// Diet editors (S0 Diet group): frequency caps, and the ingredients you exclude or dislike.
import { useState } from "react";

import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { Segmented } from "@/components/ui/Segmented";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { Stepper } from "@/components/ui/Stepper";
import { api } from "@/lib/api/client";
import type { IngredientHit, SettingsOut, UserSettings } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";
import { CAP_MEALS } from "@/lib/settings/fields";

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

type Kind = "exclude" | "dislike";
const KINDS: { value: Kind; label: string }[] = [
  { value: "exclude", label: "Never use" },
  { value: "dislike", label: "Use less" },
];

/** Your exclude and dislike decisions. Each change is saved at once (an ingredient decision, not a setting). */
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
      title="Excluded and disliked"
      why="Never use keeps an ingredient out of everything; use less lets it in only when nothing else fits."
      onBack={onDone}
      primaryLabel="Done"
      onPrimary={onDone}
    >
      {!loaded.data ? (
        loaded.error ? <ErrorState error={loaded.error} onRetry={() => void loaded.reload()} /> : <Skeleton cards={1} />
      ) : (
        <>
          {mine.length === 0 && <p className="muted">Nothing here yet.</p>}
          <ul className="list">
            {mine.map((p) => (
              <li key={p.ingredient_id} className={styles.row}>
                <span>
                  <strong>{p.name}</strong> <span className="badge">{p.preference === "exclude" ? "Never use" : "Use less"}</span>
                </span>
                <button type="button" className="btn btn-small" disabled={busy || !online} onClick={() => void set(p.ingredient_id, null)}>
                  Remove
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
