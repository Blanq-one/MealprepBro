"use client";

import { useState } from "react";

import { useOnline } from "@/components/AppShell";
import { NLQuickAdd } from "@/components/NLQuickAdd";
import { AddFlow } from "@/components/pantry/AddFlow";
import { CorrectAmountSheet } from "@/components/pantry/CorrectAmountSheet";
import { IngredientSearch } from "@/components/pantry/IngredientSearch";
import { LotBadges } from "@/components/pantry/LotBadges";
import { VersionSheet } from "@/components/pantry/VersionSheet";
import { ProblemNotice, SyncNote } from "@/components/Status";
import { Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api/client";
import type { InventoryLot, QuickPick, StorageLocation } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";

import styles from "./pantry.module.css";

const LOCATIONS: { key: StorageLocation; label: string }[] = [
  { key: "fridge", label: "Fridge" },
  { key: "freezer", label: "Freezer" },
  { key: "pantry", label: "Pantry" },
];

// P0 Pantry (FLOW_SPEC §9): items by location. Adding (a quick pick or a typed name) opens the add flow
// (J4–J5: version, form, package size, Custom or Not sure); an estimated amount can be corrected, and a held
// item that comes in versions can be set to the version on its label.
export default function PantryPage() {
  const lots = useApi<InventoryLot[]>("/api/v1/inventory");
  const picks = useApi<QuickPick[]>("/api/v1/inventory/quick-picks");
  const [error, setError] = useState<unknown>(null);
  const [added, setAdded] = useState<string | null>(null);
  const [adding, setAdding] = useState<{ id: number; name: string } | null>(null);
  const [correcting, setCorrecting] = useState<InventoryLot | null>(null);
  const [versioning, setVersioning] = useState<InventoryLot | null>(null);
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

      <section className="card" aria-label="Add">
        <IngredientSearch label="Add by name" onPick={(hit) => setAdding({ id: hit.id, name: hit.name })} disabled={!online} />
        {picks.data && picks.data.length > 0 && (
          <>
            <h2 className={styles.quickTitle}>Quick add</h2>
            <div className={styles.chips}>
              {picks.data.map((pick) => (
                <button key={`${pick.ingredient_id}-${pick.product_id ?? 0}`} type="button" className="btn btn-small" disabled={!online} onClick={() => setAdding({ id: pick.ingredient_id, name: pick.name })}>
                  + {pick.name}
                </button>
              ))}
            </div>
          </>
        )}
      </section>

      <AddFlow
        ingredient={adding}
        context="pantry"
        online={online}
        onClose={() => setAdding(null)}
        onAdded={(out) => {
          setAdding(null);
          setAdded(`Added ${out.map((l) => `${l.name} (${l.display}${l.quantity_is_estimate ? ", estimated" : ""})`).join(", ")}`);
          void lots.reload();
        }}
      />
      <CorrectAmountSheet
        lot={correcting}
        online={online}
        onClose={() => setCorrecting(null)}
        onChanged={(lot) => {
          setCorrecting(null);
          setAdded(`${lot.name}: now ${lot.display}`);
          void lots.reload();
        }}
      />
      <VersionSheet
        lot={versioning}
        online={online}
        onClose={() => setVersioning(null)}
        onChanged={(lot) => {
          setVersioning(null);
          setAdded(`Now ${lot.name} (${lot.display})`);
          void lots.reload();
        }}
      />

      <NLQuickAdd
        onAdded={(out) => {
          setAdded(`Added ${out.length} item${out.length === 1 ? "" : "s"}`);
          void lots.reload();
        }}
      />

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
                        <LotBadges lot={lot} />
                      </div>
                      {lot.notes && <p className="small muted">{lot.notes}</p>}
                      <div className="row" style={{ flexWrap: "wrap", marginTop: 4 }}>
                        {lot.quantity_is_estimate && (
                          <button type="button" className="btn btn-small" disabled={!online} onClick={() => setCorrecting(lot)}>
                            Correct amount
                          </button>
                        )}
                        {lot.state === "held" && lot.has_versions && (
                          <button type="button" className="btn btn-small" disabled={!online} onClick={() => setVersioning(lot)}>
                            Which version?
                          </button>
                        )}
                      </div>
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
