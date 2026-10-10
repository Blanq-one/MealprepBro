"use client";

import { useEffect, useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { NeedsConnection } from "@/components/ui/States";
import { api, describeError } from "@/lib/api/client";
import type { AddOptions, InventoryLot, VersionChoice } from "@/lib/api/types";
import { usualVersions } from "@/lib/cook/usualVersions";

import { VersionChoices } from "./VersionChoices";

/** "Which version?" for a held lot already in your pantry (J4): the lot becomes the version on its label.
 * Not sure leaves it held; the generic item is never allowed by this. */
export function VersionSheet({ lot, online, onClose, onChanged }: { lot: InventoryLot | null; online: boolean; onClose: () => void; onChanged: (lot: InventoryLot) => void }) {
  const [options, setOptions] = useState<AddOptions | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setOptions(null);
    setError(null);
    if (!lot) return;
    let live = true;
    api<AddOptions>(`/api/v1/ingredients/${lot.ingredient_id}/add-options`)
      .then((out) => live && setOptions(out))
      .catch((e: unknown) => live && setError(e));
    return () => {
      live = false;
    };
  }, [lot]);

  if (!lot) return null;

  async function pick(choice: VersionChoice) {
    if (!lot) return;
    if (choice.ingredient_id === null) {
      onClose(); // not sure: it stays held
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onChanged(await api<InventoryLot>(`/api/v1/inventory/${lot.id}/version`, { method: "POST", json: { ingredient_id: choice.ingredient_id } }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet title={`${lot.name}: which version?`} open onClose={onClose}>
      {!options && error === null && <p className="muted">Loading…</p>}
      {options?.versions && (
        <VersionChoices versions={options.versions} selected={null} onPick={(c) => void pick(c)} disabled={busy || !online} usual={usualVersions()[String(lot.ingredient_id)] ?? null} />
      )}
      {error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
      {!online && <NeedsConnection />}
    </BottomSheet>
  );
}
