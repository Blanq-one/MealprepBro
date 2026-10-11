"use client";

import { useEffect, useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Segmented } from "@/components/ui/Segmented";
import { NeedsConnection } from "@/components/ui/States";
import { Stepper } from "@/components/ui/Stepper";
import { api, describeError } from "@/lib/api/client";
import type { CorrectOptions, InventoryLot } from "@/lib/api/types";

import styles from "./AddFlow.module.css";

const CUSTOM_MAX = 9999;

/** What you picked: a fraction of the package it came in, another package size, or a custom amount. */
export type Correction = { kind: "fraction"; key: string } | { kind: "preset"; key: string } | { kind: "custom" };

/** The PATCH body for a correction. The server works out every amount (M2). */
export function correctionBody(choice: Correction, custom: { amount: number; unit: string } | null): Record<string, string> | null {
  if (choice.kind === "fraction") return { package_fraction: choice.key };
  if (choice.kind === "preset") return { preset: choice.key };
  return custom ? { quantity: String(custom.amount), unit: custom.unit } : null;
}

/** Correct amount, for any lot (M2): quick taps for ¾, ½ and ¼ of the package it came in, a different package
 * size, or a custom amount. Every option and its display string come from GET /inventory/{id}/correct-options. */
export function CorrectAmountSheet({ lot, online, onClose, onChanged }: { lot: InventoryLot | null; online: boolean; onClose: () => void; onChanged: (lot: InventoryLot) => void }) {
  const [options, setOptions] = useState<CorrectOptions | null>(null);
  const [choice, setChoice] = useState<Correction | null>(null);
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
    api<CorrectOptions>(`/api/v1/inventory/${lot.id}/correct-options`)
      .then((out) => {
        if (!live) return;
        setOptions(out);
        const first = out.custom_units[0];
        setUnit(first?.unit ?? "");
        setAmount(first ? Number(first.start) : null);
      })
      .catch((e: unknown) => live && setError(e));
    return () => {
      live = false;
    };
  }, [lot]);

  if (!lot) return null;
  const customUnit = options?.custom_units.find((u) => u.unit === unit);
  const step = customUnit ? Number(customUnit.step) : 1;
  const custom = choice?.kind === "custom" && amount !== null && amount > 0 && customUnit ? { amount, unit } : null;
  const body = choice ? correctionBody(choice, custom) : null;
  const on = (kind: Correction["kind"], key = "") => choice !== null && choice.kind === kind && (kind === "custom" || ("key" in choice && choice.key === key));

  async function save() {
    if (!lot || !body) return;
    setBusy(true);
    setError(null);
    try {
      onChanged(await api<InventoryLot>(`/api/v1/inventory/${lot.id}`, { method: "PATCH", json: body }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet title={`${lot.name}: how much is there?`} open onClose={onClose}>
      {!options && error === null && <p className="muted">Loading…</p>}
      {options && (
        <>
          <p className="small muted">
            Now: {options.display}
            {options.estimated ? " (estimated)" : ""}
          </p>
          {options.fractions.length > 0 && (
            <>
              <p className={styles.label}>What&apos;s left of {options.package_display}?</p>
              <div className={styles.amounts} role="group" aria-label="What's left">
                {options.fractions.map((f) => (
                  <button key={f.key} type="button" className={on("fraction", f.key) ? `${styles.amount} ${styles.amountOn}` : styles.amount} aria-pressed={on("fraction", f.key)} onClick={() => setChoice({ kind: "fraction", key: f.key })}>
                    {f.display}
                  </button>
                ))}
              </div>
            </>
          )}
          {options.presets.length > 0 && (
            <>
              <p className={styles.label}>A different package</p>
              <div className={styles.amounts} role="group" aria-label="A different package">
                {options.presets.map((preset) => (
                  <button key={preset.key} type="button" className={on("preset", preset.key) ? `${styles.amount} ${styles.amountOn}` : styles.amount} aria-pressed={on("preset", preset.key)} onClick={() => setChoice({ kind: "preset", key: preset.key })}>
                    {preset.label}
                  </button>
                ))}
              </div>
            </>
          )}
          {options.custom_units.length > 0 && (
            <div className={styles.amounts}>
              <button type="button" className={on("custom") ? `${styles.amount} ${styles.amountOn}` : styles.amount} aria-pressed={on("custom")} onClick={() => setChoice({ kind: "custom" })}>
                Custom
              </button>
            </div>
          )}
          {choice?.kind === "custom" && customUnit && (
            <>
              <Stepper size="compact" label="Custom amount" value={amount} unit={customUnit.label} min={step} max={CUSTOM_MAX} step={step} decimal onChange={setAmount} />
              {options.custom_units.length > 1 && (
                <Segmented
                  label="Unit"
                  options={options.custom_units.map((u) => ({ value: u.unit, label: u.label }))}
                  value={unit}
                  onChange={(next) => {
                    const picked = options.custom_units.find((u) => u.unit === next);
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
      <button type="button" className={`btn btn-primary btn-block ${styles.add}`} onClick={() => void save()} disabled={busy || body === null || !online}>
        {busy ? "Saving…" : "Save"}
      </button>
      {!online && <NeedsConnection />}
    </BottomSheet>
  );
}
