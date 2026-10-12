"use client";

import { useState } from "react";

import { AddFlow } from "@/components/pantry/AddFlow";
import { IngredientSearch } from "@/components/pantry/IngredientSearch";
import { LotBadges } from "@/components/pantry/LotBadges";
import { VersionSheet } from "@/components/pantry/VersionSheet";
import { Chips } from "@/components/ui/Chips";
import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { Skeleton } from "@/components/ui/States";
import { ToggleRow } from "@/components/ui/ToggleRow";
import type { AlwaysHaveOption, InventoryLot, LastSearch, QuickPick, StorageLocation } from "@/lib/api/types";
import type { DraftExtra, MealNowDraft } from "@/lib/cook/answers";
import { useApi } from "@/lib/hooks/useApi";

import styles from "./Ask.module.css";

const LOCATIONS: { key: StorageLocation; label: string }[] = [
  { key: "fridge", label: "Fridge" },
  { key: "freezer", label: "Freezer" },
  { key: "pantry", label: "Pantry" },
];
const ALWAYS_SHOWN = 3;

type Row = { key: string; ingredientId: number; name: string; lots: InventoryLot[] };

/** Your pantry by location, one row per item: its lots' amounts and badges (each lot as the server shows it). */
export function pantryRows(lots: readonly InventoryLot[], location: StorageLocation): Row[] {
  const rows = new Map<number, Row>();
  for (const lot of lots) {
    if (lot.location !== location) continue;
    const row = rows.get(lot.ingredient_id) ?? { key: `${location}-${lot.ingredient_id}`, ingredientId: lot.ingredient_id, name: lot.name, lots: [] };
    row.lots.push(lot);
    rows.set(lot.ingredient_id, row);
  }
  return [...rows.values()];
}

function extraLabel(extra: DraftExtra): string {
  if (extra.status === "could_buy") return `${extra.name} · could buy`;
  return extra.presetLabel ? `${extra.name} · have it, ${extra.presetLabel}` : `${extra.name} · have it`;
}

/** "Always have: rice, oil, salt and 9 more" (C3): staples that always count as in stock. */
export function alwaysHaveLine(names: readonly string[]): string {
  const shown = names.slice(0, ALWAYS_SHOWN).join(", ");
  const more = names.length - ALWAYS_SHOWN;
  return more > 0 ? `Always have: ${shown} and ${more} more` : `Always have: ${shown}`;
}

/** What C3 edits in either draft (a meal now or meal prep): pantry items turned off, and items added. */
export type HaveDraft = Pick<MealNowDraft, "off" | "extras">;

/** C3 What do you have? Pantry toggles (on by default; off = not for this search), Always have in one line,
 * typed and quick add (Have it / Could buy, with the add flow's versions, forms and amounts), and last time's
 * extras as chips. Meal now: "Find recipes"; meal prep: "Next" (to C3b). */
export function HaveStep<D extends HaveDraft>({
  draft,
  onChange,
  online,
  last,
  onBack,
  onFind,
  primaryLabel = "Find recipes",
  progress = { step: 2, total: 2 },
  sends = true,
}: {
  draft: D;
  onChange: (draft: D) => void;
  online: boolean;
  last: LastSearch | null;
  onBack: () => void;
  onFind: () => void;
  primaryLabel?: string;
  progress?: { step: number; total: number };
  /** The button sends the search (meal now), so it needs a connection; meal prep's goes on to C3b. */
  sends?: boolean;
}) {
  const lots = useApi<InventoryLot[]>("/api/v1/inventory");
  const always = useApi<AlwaysHaveOption[]>("/api/v1/settings/always-have");
  const picks = useApi<QuickPick[]>("/api/v1/inventory/quick-picks");
  const [adding, setAdding] = useState<{ id: number; name: string } | null>(null);
  const [versioning, setVersioning] = useState<InventoryLot | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const off = new Set(draft.off);
  const extras = new Set(draft.extras.map((e) => e.ingredient_id));
  const alwaysNames = (always.data ?? []).filter((o) => o.selected).map((o) => o.name);
  const fromLast = (last?.extras ?? []).filter((e) => !extras.has(e.ingredient_id));

  function toggle(ingredientId: number, on: boolean) {
    const next = draft.off.filter((id) => id !== ingredientId);
    onChange({ ...draft, off: on ? next : [...next, ingredientId] });
  }

  function addExtra(extra: DraftExtra) {
    onChange({ ...draft, extras: [...draft.extras.filter((e) => e.ingredient_id !== extra.ingredient_id), extra] });
  }

  return (
    <QuestionScreen
      title="What do you have?"
      why="I'll use these first. 'Could buy' items are things you're happy to pick up."
      progress={progress}
      onBack={onBack}
      primaryLabel={primaryLabel}
      onPrimary={onFind}
      primaryDisabled={!online && sends}
      footerNote={!online && sends ? "Needs a connection" : undefined}
    >
      {note && (
        <p className="notice" role="status">
          {note}
        </p>
      )}
      {lots.loading && !lots.data && <Skeleton cards={2} label="Loading your pantry" />}
      {lots.data && lots.data.length === 0 && <p className="notice">Your pantry is empty. Add what you have, or skip and I&apos;ll show what to buy.</p>}
      {lots.data &&
        LOCATIONS.map(({ key, label }) => {
          const rows = pantryRows(lots.data ?? [], key);
          if (rows.length === 0) return null;
          return (
            <section key={key} className={styles.group} aria-label={label}>
              <h2 className={styles.groupTitle}>{label}</h2>
              {rows.map((row) => {
                const unusable = row.lots.every((l) => l.state === "held" || l.state === "excluded");
                const versioned = row.lots.find((l) => l.state === "held" && l.has_versions);
                return (
                  <div key={row.key}>
                    <ToggleRow
                      label={row.name}
                      detail={row.lots.map((l) => l.display).join(" + ")}
                      badges={row.lots.map((l) => (
                        <LotBadges key={l.id} lot={l} />
                      ))}
                      checked={!unusable && !off.has(row.ingredientId)}
                      disabled={unusable}
                      onChange={(on) => toggle(row.ingredientId, on)}
                    />
                    {versioned && (
                      <button type="button" className="btn btn-small" disabled={!online} onClick={() => setVersioning(versioned)}>
                        Which version?
                      </button>
                    )}
                  </div>
                );
              })}
            </section>
          );
        })}
      {alwaysNames.length > 0 && (
        <details className={styles.always}>
          <summary>{alwaysHaveLine(alwaysNames)}</summary>
          <p className="small muted">{alwaysNames.join(", ")}. These always count as in stock; change them in Settings.</p>
        </details>
      )}

      <section className={styles.group} aria-label="Add something">
        <IngredientSearch onPick={(hit) => setAdding({ id: hit.id, name: hit.name })} disabled={!online} />
        {picks.data && picks.data.length > 0 && (
          <Chips
            label="Your usual items"
            chips={picks.data.filter((p) => !extras.has(p.ingredient_id)).map((p) => ({ key: String(p.ingredient_id), label: `+ ${p.name}` }))}
            onPick={(key) => {
              const pick = picks.data?.find((p) => String(p.ingredient_id) === key);
              if (pick) setAdding({ id: pick.ingredient_id, name: pick.name });
            }}
          />
        )}
        <Chips
          label="Added for this search"
          chips={draft.extras.map((e) => ({ key: String(e.ingredient_id), label: extraLabel(e) }))}
          onRemove={(key) => onChange({ ...draft, extras: draft.extras.filter((e) => String(e.ingredient_id) !== key) })}
        />
        {fromLast.length > 0 && (
          <>
            <p className={styles.label}>From last time</p>
            <Chips
              label="From last time"
              chips={fromLast.map((e) => ({ key: String(e.ingredient_id), label: `${e.name} · ${e.status === "have" ? "have it" : "could buy"}` }))}
              onPick={(key) => {
                const e = fromLast.find((x) => String(x.ingredient_id) === key);
                if (e) addExtra({ ingredient_id: e.ingredient_id, name: e.name, status: e.status });
              }}
            />
          </>
        )}
      </section>

      <AddFlow
        ingredient={adding}
        context="have"
        online={online}
        onClose={() => setAdding(null)}
        onExtra={(extra) => {
          setAdding(null);
          addExtra(extra);
        }}
        onAdded={(out) => {
          setAdding(null);
          const added = new Set(out.map((l) => l.ingredient_id));
          onChange({ ...draft, off: draft.off.filter((id) => !added.has(id)), extras: draft.extras.filter((e) => !added.has(e.ingredient_id)) });
          setNote(`Added to your pantry: ${out.map((l) => `${l.name} (${l.display})`).join(", ")}`);
          void lots.reload();
        }}
      />
      <VersionSheet
        lot={versioning}
        online={online}
        onClose={() => setVersioning(null)}
        onChanged={(lot) => {
          setVersioning(null);
          setNote(`Now ${lot.name} (${lot.display})`);
          void lots.reload();
        }}
      />
    </QuestionScreen>
  );
}
