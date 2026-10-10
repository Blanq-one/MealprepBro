"use client";

import { type FormEvent, useState } from "react";

import { useOnline } from "@/components/AppShell";
import { NLQuickAdd } from "@/components/NLQuickAdd";
import { AmountPicker } from "@/components/pantry/AmountPicker";
import { ProblemNotice, SyncNote } from "@/components/Status";
import { Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api/client";
import type { IngredientHit, InventoryLot, InventoryLotIn, QuickPick, StorageLocation } from "@/lib/api/types";
import { daysUntil, shortDate } from "@/lib/format/dates";
import { useApi } from "@/lib/hooks/useApi";

import styles from "./pantry.module.css";

const LOCATIONS: { key: StorageLocation; label: string }[] = [
  { key: "fridge", label: "Fridge" },
  { key: "freezer", label: "Freezer" },
  { key: "pantry", label: "Pantry" },
];
const UNITS = ["g", "kg", "oz", "lb", "ml", "l", "cup", "tbsp", "tsp", "count"];
const USE_SOON_DAYS = 3;

function ExpiryBadge({ lot }: { lot: InventoryLot }) {
  if (!lot.expires_on) return null;
  const days = daysUntil(lot.expires_on);
  const estimate = lot.expiry_is_estimate ? " (est.)" : "";
  if (days < 0) return <span className="badge badge-danger">Past use-by {shortDate(lot.expires_on)}</span>;
  if (days <= USE_SOON_DAYS) return <span className="badge badge-warn">Use soon: {shortDate(lot.expires_on)}{estimate}</span>;
  return <span className="badge">Use by {shortDate(lot.expires_on)}{estimate}</span>;
}

async function addLots(items: InventoryLotIn[], source: "quick_add" | "parse"): Promise<InventoryLot[]> {
  return api<InventoryLot[]>("/api/v1/inventory/bulk", { method: "POST", json: { items, source } });
}

function SearchAdd({ onAdded }: { onAdded: () => void }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<IngredientHit[]>([]);
  const [picked, setPicked] = useState<IngredientHit | null>(null);
  const [amount, setAmount] = useState("");
  const [unit, setUnit] = useState("lb");
  const [location, setLocation] = useState<StorageLocation>("fridge");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function search(value: string) {
    setQuery(value);
    setPicked(null);
    if (value.trim().length < 2) {
      setHits([]);
      return;
    }
    try {
      setHits(await api<IngredientHit[]>(`/api/v1/ingredients?q=${encodeURIComponent(value.trim())}&limit=6`));
    } catch (e) {
      setError(e);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!picked || !/^\d+(\.\d+)?$/.test(amount.trim())) return;
    setBusy(true);
    setError(null);
    try {
      await addLots(
        [{ ingredient_id: picked.id, quantity: amount.trim(), unit, location, expiry_is_estimate: true }],
        "quick_add",
      );
      setQuery("");
      setHits([]);
      setPicked(null);
      setAmount("");
      onAdded();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={add} aria-label="Add by name">
      <h2>Add by name</h2>
      <label htmlFor="search" className="sr-only">
        Ingredient
      </label>
      <input id="search" placeholder="Search: chicken, rice, eggs…" value={query} onChange={(e) => void search(e.target.value)} />
      {!picked && hits.length > 0 && (
        <ul className="list">
          {hits.map((hit) => (
            <li key={hit.id}>
              <button
                type="button"
                className={`btn btn-block ${styles.hit}`}
                disabled={hit.status === "excluded"}
                onClick={() => {
                  setPicked(hit);
                  setQuery(hit.name);
                }}
              >
                {hit.name}
                {hit.status !== "allowed" && <span className="badge"> {hit.status}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {picked && (
        <>
          <div className="row" style={{ marginTop: 8 }}>
            <input aria-label="Amount" inputMode="decimal" placeholder="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
            <select aria-label="Unit" value={unit} onChange={(e) => setUnit(e.target.value)} style={{ width: "6.5em" }}>
              {UNITS.map((u) => (
                <option key={u}>{u}</option>
              ))}
            </select>
            <select aria-label="Where" value={location} onChange={(e) => setLocation(e.target.value as StorageLocation)} style={{ width: "7em" }}>
              {LOCATIONS.map((l) => (
                <option key={l.key} value={l.key}>
                  {l.label.toLowerCase()}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-primary btn-block" disabled={busy || !/^\d+(\.\d+)?$/.test(amount.trim())} style={{ marginTop: 8 }}>
            Add {picked.name}
          </button>
        </>
      )}
      <ProblemNotice error={error} />
    </form>
  );
}

// P0 Pantry (FLOW_SPEC §9): the Phase 2 inventory screen; a quick pick opens the amount picker (P1).
export default function PantryPage() {
  const lots = useApi<InventoryLot[]>("/api/v1/inventory");
  const picks = useApi<QuickPick[]>("/api/v1/inventory/quick-picks");
  const [error, setError] = useState<unknown>(null);
  const [added, setAdded] = useState<string | null>(null);
  const [picking, setPicking] = useState<QuickPick | null>(null);
  const online = useOnline();

  async function discard(lot: InventoryLot) {
    setError(null);
    try {
      await api(`/api/v1/inventory/${lot.id}/discard`, { method: "POST", json: { reason: "waste" } });
      await lots.reload();
    } catch (e) {
      setError(e);
    }
  }

  return (
    <>
      <h1>Pantry</h1>
      <SyncNote syncedAt={lots.syncedAt} fromCache={lots.fromCache} />
      <ProblemNotice error={error ?? lots.error} />
      {added && (
        <p className="notice" role="status">
          {added}
        </p>
      )}

      {picks.data && picks.data.length > 0 && (
        <section className="card" aria-label="Quick add">
          <h2>Quick add</h2>
          <div className={styles.chips}>
            {picks.data.map((pick) => (
              <button key={`${pick.ingredient_id}-${pick.product_id ?? 0}`} type="button" className="btn btn-small" onClick={() => setPicking(pick)}>
                + {pick.name}
                <span className="muted small"> {pick.display}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <AmountPicker
        pick={picking}
        online={online}
        onClose={() => setPicking(null)}
        onAdded={(out) => {
          setPicking(null);
          setAdded(`Added ${out.map((l) => `${l.name} (${l.display})`).join(", ")}`);
          void lots.reload();
        }}
      />

      <NLQuickAdd
        onAdded={(out) => {
          setAdded(`Added ${out.length} item${out.length === 1 ? "" : "s"}`);
          void lots.reload();
        }}
      />
      <SearchAdd onAdded={() => void lots.reload()} />

      {lots.loading && !lots.data && <Skeleton cards={3} label="Loading your pantry" />}
      {lots.data &&
        LOCATIONS.map(({ key, label }) => {
          const here = lots.data?.filter((l) => l.location === key) ?? [];
          return (
            <section key={key} className="card" aria-label={label}>
              <h2>
                {label} <span className="muted small">{here.length}</span>
              </h2>
              {here.length === 0 && <p className="muted small">Nothing here.</p>}
              <ul className="list">
                {here.map((lot) => (
                  <li key={lot.id} className={styles.lot}>
                    <div>
                      <strong>{lot.name}</strong> <span>{lot.display}</span>
                      <div className="row" style={{ flexWrap: "wrap", marginTop: 2 }}>
                        {lot.opened_on && <span className="badge badge-accent">Open package</span>}
                        <ExpiryBadge lot={lot} />
                      </div>
                      {lot.notes && <p className="small muted">{lot.notes}</p>}
                    </div>
                    <button type="button" className="btn btn-small btn-danger" onClick={() => void discard(lot)} aria-label={`Throw out ${lot.name}`}>
                      Toss
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
    </>
  );
}
