"use client";

import { useEffect, useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Segmented } from "@/components/ui/Segmented";
import { NeedsConnection } from "@/components/ui/States";
import { Stepper } from "@/components/ui/Stepper";
import { api, describeError } from "@/lib/api/client";
import type { AddOptions, InventoryLot } from "@/lib/api/types";

import styles from "./AddFlow.module.css";

const CUSTOM_MAX = 9999;

/** Correct a "Not sure" amount (J5): pick the package you really have, or a custom amount. The server converts
 * it and clears the estimate. */
export function CorrectAmountSheet({ lot, online, onClose, onChanged }: { lot: InventoryLot | null; online: boolean; onClose: () => void; onChanged: (lot: InventoryLot) => void }) {
  const [options, setOptions] = useState<AddOptions | null>(null);
  const [choice, setChoice] = useState<string | null>(null); // a preset key, or "custom"
  const [unit, setUnit] = useState("");
  const [amount, setAmount] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setOptions(null);
    setChoice(null);
    setError(null);
    if (!lot) return;
    let live = true;
    api<AddOptions>(`/api/v1/ingredients/${lot.ingredient_id}/add-options`)
      .then((out) => {
        if (!live) return;
        setOptions(out);
        const form = out.forms.find((f) => f.ingredient_id === lot.ingredient_id) ?? out.forms[0];
        const first = form?.custom_units[0];
        setUnit(first?.unit ?? "");
        setAmount(first ? Number(first.start) : null);
      })
      .catch((e: unknown) => live && setError(e));
    return () => {
      live = false;
    };
  }, [lot]);

  if (!lot) return null;
  const form = options ? (options.forms.find((f) => f.ingredient_id === lot.ingredient_id) ?? options.forms[0] ?? null) : null;
  const customUnit = form?.custom_units.find((u) => u.unit === unit);
  const step = customUnit ? Number(customUnit.step) : 1;
  const ready = choice !== null && (choice !== "custom" || (customUnit !== undefined && amount !== null && amount > 0));

  async function save() {
    if (!lot || !ready) return;
    setBusy(true);
    setError(null);
    try {
      const body = choice === "custom" ? { quantity: String(amount), unit } : { preset: choice };
      onChanged(await api<InventoryLot>(`/api/v1/inventory/${lot.id}`, { method: "PATCH", json: body }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet title={`${lot.name}: how much is there?`} open onClose={onClose}>
      <p className="small muted">Now: {lot.display} (estimated)</p>
      {!form && error === null && <p className="muted">Loading…</p>}
      {form && (
        <>
          <div className={styles.amounts} role="group" aria-label="How much is there">
            {form.presets.map((preset) => (
              <button key={preset.key} type="button" className={choice === preset.key ? `${styles.amount} ${styles.amountOn}` : styles.amount} aria-pressed={choice === preset.key} onClick={() => setChoice(preset.key)}>
                {preset.label}
              </button>
            ))}
            {form.custom_units.length > 0 && (
              <button type="button" className={choice === "custom" ? `${styles.amount} ${styles.amountOn}` : styles.amount} aria-pressed={choice === "custom"} onClick={() => setChoice("custom")}>
                Custom
              </button>
            )}
          </div>
          {choice === "custom" && customUnit && (
            <>
              <Stepper size="compact" label="Custom amount" value={amount} unit={customUnit.label} min={step} max={CUSTOM_MAX} step={step} decimal onChange={setAmount} />
              {form.custom_units.length > 1 && (
                <Segmented
                  label="Unit"
                  options={form.custom_units.map((u) => ({ value: u.unit, label: u.label }))}
                  value={unit}
                  onChange={(next) => {
                    const picked = form.custom_units.find((u) => u.unit === next);
                    setUnit(next);
                    setAmount(picked ? Number(picked.start) : null);
                  }}
                />
              )}
            </>
          )}
        </>
      )}
      {error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
      <button type="button" className={`btn btn-primary btn-block ${styles.add}`} onClick={() => void save()} disabled={busy || !ready || !online}>
        {busy ? "Saving…" : "Save"}
      </button>
      {!online && <NeedsConnection />}
    </BottomSheet>
  );
}
