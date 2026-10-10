"use client";

import { useState } from "react";

import { api, describeError } from "@/lib/api/client";
import type { IngredientHit } from "@/lib/api/types";

import styles from "./IngredientSearch.module.css";

const STATUS_BADGES: Record<string, string> = { excluded: "off your list", held: "held" };

/** Typed entry with autocomplete from the ingredient list (C3, P0). A pick opens the add flow, which says what
 * an excluded or held item means. */
export function IngredientSearch({ onPick, disabled, label = "Add something" }: { onPick: (hit: IngredientHit) => void; disabled?: boolean; label?: string }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<IngredientHit[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function search(value: string) {
    setQuery(value);
    setError(null);
    if (value.trim().length < 2) {
      setHits(null);
      return;
    }
    try {
      const found = await api<IngredientHit[]>(`/api/v1/ingredients?q=${encodeURIComponent(value.trim())}&limit=6`);
      setHits(found);
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className={styles.search}>
      <label htmlFor="ingredient-search" className={styles.label}>
        {label}
      </label>
      <input
        id="ingredient-search"
        placeholder="Search: chicken, rice, eggs…"
        value={query}
        disabled={disabled}
        autoComplete="off"
        onChange={(e) => void search(e.target.value)}
      />
      {hits && hits.length === 0 && <p className="small muted">No match for &lsquo;{query.trim()}&rsquo;. Try another name.</p>}
      {hits && hits.length > 0 && (
        <ul className={styles.hits} aria-label="Matches">
          {hits.map((hit) => (
            <li key={hit.id}>
              <button
                type="button"
                className={styles.hit}
                onClick={() => {
                  onPick(hit);
                  setQuery("");
                  setHits(null);
                }}
              >
                {hit.name}
                {STATUS_BADGES[hit.status] && <span className="badge"> {STATUS_BADGES[hit.status]}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
    </div>
  );
}
