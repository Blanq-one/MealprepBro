"use client";

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { InventoryLot, InventoryLotIn, ParsedLot, ParseResult, StorageLocation } from "@/lib/api/types";

import { ProblemNotice } from "./Status";
import styles from "./NLQuickAdd.module.css";

const UNITS = ["g", "kg", "oz", "lb", "ml", "l", "cup", "tbsp", "tsp", "count", "clove", "can"];
const NUMBER = /^\d+(\.\d+)?$/;

type Draft = {
  item: ParsedLot;
  selected: boolean;
  ingredientId: number | null;
  ingredientName: string | null;
  amount: string; // typed by you; empty = the parsed amount
  unit: string;
  location: StorageLocation;
};

function draftOf(item: ParsedLot): Draft {
  return {
    item,
    selected: item.status === "ok",
    ingredientId: item.ingredient_id ?? null,
    ingredientName: item.ingredient_name ?? null,
    amount: "",
    unit: item.unit ?? "count",
    location: item.location ?? "fridge",
  };
}

function saveable(d: Draft): boolean {
  if (d.item.status === "excluded" || d.ingredientId === null) return false;
  if (d.amount.trim()) return NUMBER.test(d.amount.trim());
  return d.item.quantity !== null && d.item.quantity !== undefined && d.item.status !== "unresolved";
}

export function toLot(d: Draft): InventoryLotIn {
  const typed = d.amount.trim();
  return {
    ingredient_id: d.ingredientId as number,
    // typed amounts go to the server as written; it converts units (the app does no unit math)
    quantity: typed || String(d.item.quantity),
    unit: typed ? d.unit : (d.item.unit ?? d.unit),
    location: d.location,
    product_id: typed ? null : (d.item.product_id ?? null),
    expiry_is_estimate: true,
  };
}

/** Type what you have ("2 lb chicken thighs and half a cabbage"); check the preview; nothing is saved until
 * you tap Add. */
export function NLQuickAdd({ onAdded }: { onAdded: (lots: InventoryLot[]) => void }) {
  const [text, setText] = useState("");
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function read() {
    setBusy(true);
    setError(null);
    try {
      const out = await api<ParseResult>("/api/v1/inventory/parse", { method: "POST", json: { text } });
      setDrafts(out.items.map(draftOf));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  function update(index: number, changes: Partial<Draft>) {
    setDrafts((ds) => (ds ? ds.map((d, i) => (i === index ? { ...d, ...changes } : d)) : ds));
  }

  const chosen = (drafts ?? []).filter((d) => d.selected && saveable(d));

  async function confirm() {
    if (!chosen.length) return;
    setBusy(true);
    setError(null);
    try {
      const lots = await api<InventoryLot[]>("/api/v1/inventory/bulk", {
        method: "POST",
        json: { source: "parse", items: chosen.map(toLot) },
      });
      setDrafts(null);
      setText("");
      onAdded(lots);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-label="Quick add by typing">
      <h2>Type what you have</h2>
      <label htmlFor="nl-text" className="sr-only">
        What you have
      </label>
      <textarea
        id="nl-text"
        placeholder="2 lb chicken thighs and half a cabbage"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button type="button" className="btn btn-block" onClick={read} disabled={busy || text.trim().length < 2} style={{ marginTop: 8 }}>
        {busy && !drafts ? "Reading…" : "Read it"}
      </button>
      <ProblemNotice error={error} />
      {drafts && (
        <div className={styles.preview}>
          <p className="small muted">Check each item, then add them. Nothing is saved until you tap Add.</p>
          <ul className="list">
            {drafts.map((d, i) => (
              <li key={`${d.item.text}-${i}`} className={styles.item}>
                <label className={styles.pick}>
                  <input
                    type="checkbox"
                    checked={d.selected && d.item.status !== "excluded"}
                    disabled={d.item.status === "excluded" || d.ingredientId === null}
                    onChange={(e) => update(i, { selected: e.target.checked })}
                    aria-label={`Add ${d.ingredientName ?? d.item.name_as_written}`}
                  />
                  <span>
                    <strong>{d.ingredientName ?? d.item.name_as_written}</strong>{" "}
                    {d.item.display && !d.amount && <span>{d.item.display}</span>}
                    <span className="small muted"> “{d.item.text}”</span>
                  </span>
                </label>
                {d.item.status !== "ok" && (
                  <p className={d.item.status === "excluded" ? "notice notice-danger small" : "notice notice-warn small"}>
                    {d.item.message ?? d.item.status}
                  </p>
                )}
                {d.item.status === "ok" && d.item.message && <p className="small muted">{d.item.message}</p>}
                {d.item.status === "unresolved" && (d.item.suggestions ?? []).length > 0 && (
                  <div className="row" style={{ flexWrap: "wrap" }}>
                    {(d.item.suggestions ?? []).map((s) => (
                      <button
                        key={s.ingredient_id}
                        type="button"
                        className="btn btn-small"
                        aria-pressed={d.ingredientId === s.ingredient_id}
                        onClick={() => update(i, { ingredientId: s.ingredient_id, ingredientName: s.name })}
                      >
                        {s.name}
                      </button>
                    ))}
                  </div>
                )}
                {d.item.status !== "excluded" && d.ingredientId !== null && (
                  <div className="row">
                    <input
                      aria-label="Amount"
                      inputMode="decimal"
                      placeholder={d.item.display ?? "Amount"}
                      value={d.amount}
                      onChange={(e) => update(i, { amount: e.target.value })}
                    />
                    <select aria-label="Unit" value={d.unit} onChange={(e) => update(i, { unit: e.target.value })} style={{ width: "6.5em" }}>
                      {UNITS.map((u) => (
                        <option key={u} value={u}>
                          {u}
                        </option>
                      ))}
                    </select>
                    <select
                      aria-label="Where"
                      value={d.location}
                      onChange={(e) => update(i, { location: e.target.value as StorageLocation })}
                      style={{ width: "7em" }}
                    >
                      <option value="fridge">fridge</option>
                      <option value="freezer">freezer</option>
                      <option value="pantry">pantry</option>
                    </select>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <button type="button" className="btn btn-primary btn-block" onClick={confirm} disabled={busy || !chosen.length}>
            Add {chosen.length} item{chosen.length === 1 ? "" : "s"}
          </button>
        </div>
      )}
    </section>
  );
}
