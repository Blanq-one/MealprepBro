"use client";

// S2 Always have (FLOW_SPEC §10): staples that always count as in stock. A searchable list with switches,
// common staples first; Save sends the list (PATCH /settings {always_have}).
import { useEffect, useState } from "react";

import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { ToggleRow } from "@/components/ui/ToggleRow";
import { api } from "@/lib/api/client";
import type { AlwaysHaveOption, SettingsOut } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";
import { errorsFromProblem, messagesFor } from "@/lib/settings/fields";

import styles from "./DietEditors.module.css";

export function AlwaysHaveEditor({ onDone, online }: { onDone: () => void; online: boolean }) {
  const options = useApi<AlwaysHaveOption[]>("/api/v1/settings/always-have");
  const [chosen, setChosen] = useState<string[] | null>(null);
  const [query, setQuery] = useState("");
  const [saving, setSaving] = useState(false);
  const [reasons, setReasons] = useState<string[]>([]);
  const [problem, setProblem] = useState<unknown>(null);

  useEffect(() => {
    if (options.data) setChosen((c) => c ?? options.data!.filter((o) => o.selected).map((o) => o.slug));
  }, [options.data]);

  async function save() {
    if (!chosen || !options.data) return;
    setSaving(true);
    setProblem(null);
    setReasons([]);
    try {
      const order = options.data.map((o) => o.slug).filter((slug) => chosen.includes(slug));
      await api<SettingsOut>("/api/v1/settings", { method: "PATCH", json: { always_have: order } });
      onDone();
    } catch (e) {
      const byField = errorsFromProblem(e);
      if (Object.keys(byField).length) setReasons(messagesFor(byField, ["always_have", "settings"]));
      else setProblem(e);
    } finally {
      setSaving(false);
    }
  }

  const needle = query.trim().toLowerCase();
  const shown = (options.data ?? []).filter((o) => !needle || o.name.toLowerCase().includes(needle));
  const common = shown.filter((o) => o.common);
  const rest = shown.filter((o) => !o.common);
  const toggle = (slug: string, on: boolean) => setChosen((c) => (on ? [...(c ?? []), slug] : (c ?? []).filter((s) => s !== slug)));
  const rows = (list: AlwaysHaveOption[]) =>
    list.map((o) => <ToggleRow key={o.slug} label={o.name} checked={(chosen ?? []).includes(o.slug)} onChange={(on) => toggle(o.slug, on)} />);

  return (
    <QuestionScreen
      title="Always have"
      why="These always count as in stock: never on a shopping list or 'check you have'."
      onBack={onDone}
      primaryLabel={online ? "Save" : "Needs a connection"}
      onPrimary={() => void save()}
      primaryDisabled={!online || chosen === null}
      busy={saving}
      reasons={reasons}
    >
      {!options.data ? (
        options.error ? <ErrorState error={options.error} onRetry={() => void options.reload()} /> : <Skeleton cards={3} />
      ) : (
        <>
          <label htmlFor="always-search" className="sr-only">
            Search ingredients
          </label>
          <input id="always-search" type="search" placeholder="Search: rice, oil, cumin…" value={query} onChange={(e) => setQuery(e.target.value)} />
          {common.length > 0 && (
            <section className="card" aria-label="Common staples" style={{ marginTop: 16 }}>
              <h2 className={styles.add} style={{ marginTop: 0 }}>
                Common staples
              </h2>
              {rows(common)}
            </section>
          )}
          {rest.length > 0 && (
            <section className="card" aria-label="Everything else">
              <h2 style={{ marginTop: 0 }}>Everything else</h2>
              {rows(rest)}
            </section>
          )}
          {shown.length === 0 && <p className="muted">No match for &ldquo;{query}&rdquo;. Try another name.</p>}
        </>
      )}
      {problem !== null && <ErrorState error={problem} title="Couldn't save that" onRetry={() => void save()} />}
    </QuestionScreen>
  );
}
