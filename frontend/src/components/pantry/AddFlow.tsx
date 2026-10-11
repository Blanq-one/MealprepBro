"use client";

import { useEffect, useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Segmented } from "@/components/ui/Segmented";
import { NeedsConnection } from "@/components/ui/States";
import { Stepper } from "@/components/ui/Stepper";
import { ToggleRow } from "@/components/ui/ToggleRow";
import { api, describeError } from "@/lib/api/client";
import type { AddOptions, BulkItemIn, FormOption, InventoryLot, StorageLocation, VersionChoice } from "@/lib/api/types";
import type { DraftExtra } from "@/lib/cook/answers";

import styles from "./AddFlow.module.css";
import { VersionChoices } from "./VersionChoices";

export const LOCATIONS: { value: StorageLocation; label: string }[] = [
  { value: "fridge", label: "Fridge" },
  { value: "freezer", label: "Freezer" },
  { value: "pantry", label: "Pantry" },
];
const CUSTOM_MAX = 9999;

/** The amount you picked: a package preset, Not sure (the usual size, marked as an estimate), or a custom
 * amount in one of the units the server offers. */
export type AmountChoice = { kind: "preset"; key: string } | { kind: "not_sure" } | { kind: "custom" };

/** The lot to add (POST /inventory/bulk). The server turns a preset, Not sure or a custom amount into grams. */
export function bulkItemFor(form: FormOption, amount: AmountChoice, custom: { amount: number; unit: string } | null, location: StorageLocation): BulkItemIn {
  const base = { ingredient_id: form.ingredient_id, location, expiry_is_estimate: true };
  if (amount.kind === "preset") return { ...base, preset: amount.key, not_sure: false };
  if (amount.kind === "custom" && custom) return { ...base, quantity: String(custom.amount), unit: custom.unit, not_sure: false };
  return { ...base, not_sure: true };
}

/** A "have it" item for this search only: its amount as the server gave it (a preset's stored amount), or a
 * custom amount in a server unit. */
export function extraFor(form: FormOption, status: DraftExtra["status"], amount: AmountChoice, custom: { amount: number; unit: string } | null): DraftExtra {
  const extra: DraftExtra = { ingredient_id: form.ingredient_id, name: form.name, status };
  if (status === "could_buy") return extra;
  if (amount.kind === "custom" && custom) return { ...extra, quantity: String(custom.amount), unit: custom.unit, presetLabel: null };
  const preset = amount.kind === "preset" ? form.presets.find((p) => p.key === amount.key) : form.presets.find((p) => p.default);
  if (!preset) return extra; // nothing to go on: enough for one recipe
  return {
    ...extra,
    preset: preset.key,
    presetLabel: amount.kind === "not_sure" ? `${preset.label}, not sure` : preset.label,
    quantity: preset.quantity,
    unit: preset.unit,
  };
}

function nameOf(options: AddOptions): string {
  const name = options.food ?? options.name;
  return `${name.slice(0, 1).toUpperCase()}${name.slice(1)}`;
}

/** Adding an item to Pantry ("pantry") or to "What do you have?" ("have"), J4–J5: which version (for a held
 * item that comes in versions), which form, then Have it / Could buy (C3 only) and how much: package sizes,
 * Custom, or Not sure. */
export function AddFlow({
  ingredient,
  context,
  online,
  onClose,
  onAdded,
  onExtra,
}: {
  ingredient: { id: number; name: string } | null;
  context: "pantry" | "have";
  online: boolean;
  onClose: () => void;
  onAdded: (lots: InventoryLot[]) => void;
  onExtra?: (extra: DraftExtra) => void;
}) {
  const [id, setId] = useState<number | null>(null);
  const [options, setOptions] = useState<AddOptions | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [keepGeneric, setKeepGeneric] = useState(false); // "Not sure" which version: it stays held
  const [blocked, setBlocked] = useState<string | null>(null);
  const [formKey, setFormKey] = useState<string | null>(null);
  const [status, setStatus] = useState<DraftExtra["status"]>("have");
  const [amount, setAmount] = useState<AmountChoice>({ kind: "not_sure" });
  const [unit, setUnit] = useState("");
  const [customAmount, setCustomAmount] = useState<number | null>(null);
  const [save, setSave] = useState(false);
  const [location, setLocation] = useState<StorageLocation>("fridge");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setId(ingredient?.id ?? null);
    setKeepGeneric(false);
    setBlocked(null);
    setStatus("have");
    setSave(false);
    setError(null);
  }, [ingredient]);

  /** A form's defaults: Not sure (or Custom when it has no sizes), its first custom unit, where it lives. */
  function applyForm(next: FormOption) {
    setFormKey(next.form);
    setAmount(next.presets.length > 0 ? { kind: "not_sure" } : { kind: "custom" });
    const first = next.custom_units[0];
    setUnit(first?.unit ?? "");
    setCustomAmount(first ? Number(first.start) : null);
    setLocation(next.location);
  }

  useEffect(() => {
    if (id === null) {
      setOptions(null);
      return;
    }
    let live = true;
    setOptions(null);
    setLoadError(null);
    api<AddOptions>(`/api/v1/ingredients/${id}/add-options`)
      .then((out) => {
        if (!live) return;
        setOptions(out);
        const selected = out.forms.find((f) => f.form === out.selected_form) ?? out.forms[0];
        if (selected) applyForm(selected);
      })
      .catch((e: unknown) => live && setLoadError(e));
    return () => {
      live = false;
    };
  }, [id]);

  const form = options ? (options.forms.find((f) => f.form === formKey) ?? options.forms[0] ?? null) : null;

  if (!ingredient) return null;
  const title = options ? `Add ${nameOf(options)}` : `Add ${ingredient.name}`;

  function pickVersion(choice: VersionChoice) {
    if (choice.state === "excluded") {
      setBlocked(`${choice.note}, so I won't add it.`);
      return;
    }
    if (choice.ingredient_id === null) {
      setKeepGeneric(true);
      return;
    }
    setId(choice.ingredient_id);
  }

  const askVersion = options?.versions && !keepGeneric && !blocked;
  const held = options?.state === "held" && !askVersion;
  const stop =
    blocked ??
    (options?.state === "excluded" ? options.message : null) ??
    (held && context === "have"
      ? options?.versions
        ? `${nameOf(options)} stays held until you check the label, so I won't use it this time.`
        : options?.message ?? null
      : null);

  const needsAmount = context === "pantry" || status === "have";
  const toPantry = context === "pantry" || (status === "have" && save);
  const customUnit = form?.custom_units.find((u) => u.unit === unit);
  const step = customUnit ? Number(customUnit.step) : 1;
  const customOk = amount.kind !== "custom" || (customUnit !== undefined && customAmount !== null && customAmount > 0);
  const usualPreset = form?.presets.find((p) => p.default) ?? null;

  async function confirm() {
    if (!form || !customOk) return;
    const custom = amount.kind === "custom" && customAmount !== null ? { amount: customAmount, unit } : null;
    if (!toPantry) {
      onExtra?.(extraFor(form, status, amount, custom));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const lots = await api<InventoryLot[]>("/api/v1/inventory/bulk", {
        method: "POST",
        json: { source: "quick_add", items: [bulkItemFor(form, amount, custom, location)] },
      });
      onAdded(lots);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet title={title} open onClose={onClose}>
      {!options && !loadError && <p className="muted">Loading…</p>}
      {loadError !== null && (
        <p className="notice notice-danger" role="alert">
          {online ? describeError(loadError) : "Adding an item needs a connection."}
        </p>
      )}

      {options && askVersion && options.versions && (
        <VersionChoices versions={options.versions} selected={null} onPick={pickVersion} usual={options.versions.usual ?? null} />
      )}

      {options && stop && (
        <>
          <p className="notice notice-warn" role="status">
            {stop}
          </p>
          <button type="button" className="btn btn-block" onClick={onClose}>
            Close
          </button>
        </>
      )}

      {options && form && !askVersion && !stop && (
        <>
          {held && options.message && <p className="notice notice-warn">{options.message}</p>}
          {options.forms.length > 1 && (
            <>
              <p className={styles.label}>Which kind?</p>
              <Segmented
                label="Which kind"
                options={options.forms.map((f) => ({ value: f.form, label: f.label }))}
                value={form.form}
                onChange={(key) => {
                  const next = options.forms.find((f) => f.form === key);
                  if (next) applyForm(next);
                }}
              />
            </>
          )}
          {context === "have" && (
            <>
              <p className={styles.label}>Do you have it?</p>
              <Segmented
                label="Have it or could buy"
                options={[
                  { value: "have" as const, label: "Have it" },
                  { value: "could_buy" as const, label: "Could buy" },
                ]}
                value={status}
                onChange={setStatus}
              />
              {status === "could_buy" && <p className="small muted">Its price comes from your stores.</p>}
            </>
          )}
          {needsAmount && (
            <>
              <p className={styles.label}>How much?</p>
              <div className={styles.amounts} role="group" aria-label="How much">
                {form.presets.map((preset) => {
                  const on = amount.kind === "preset" && amount.key === preset.key;
                  return (
                    <button key={preset.key} type="button" className={on ? `${styles.amount} ${styles.amountOn}` : styles.amount} aria-pressed={on} onClick={() => setAmount({ kind: "preset", key: preset.key })}>
                      {preset.label}
                    </button>
                  );
                })}
                {form.custom_units.length > 0 && (
                  <button type="button" className={amount.kind === "custom" ? `${styles.amount} ${styles.amountOn}` : styles.amount} aria-pressed={amount.kind === "custom"} onClick={() => setAmount({ kind: "custom" })}>
                    Custom
                  </button>
                )}
                {usualPreset && (
                  <button type="button" className={amount.kind === "not_sure" ? `${styles.amount} ${styles.amountOn}` : styles.amount} aria-pressed={amount.kind === "not_sure"} onClick={() => setAmount({ kind: "not_sure" })}>
                    Not sure
                  </button>
                )}
              </div>
              {amount.kind === "not_sure" && usualPreset && (
                <p className="small muted" data-testid="not-sure-note">
                  Adds the usual size ({usualPreset.label}), marked as an estimate you can correct later in Pantry.
                </p>
              )}
              {form.presets.length > 0 && <p className="small muted">Package sizes are typical US sizes (estimates).</p>}
              {amount.kind === "custom" && customUnit && (
                <>
                  <Stepper size="compact" label="Custom amount" value={customAmount} unit={customUnit.label} min={step} max={CUSTOM_MAX} step={step} decimal onChange={setCustomAmount} />
                  {form.custom_units.length > 1 && (
                    <Segmented
                      label="Unit"
                      options={form.custom_units.map((u) => ({ value: u.unit, label: u.label }))}
                      value={unit}
                      onChange={(next) => {
                        // each unit starts from the server's value for it: no conversion on the phone
                        const picked = form.custom_units.find((u) => u.unit === next);
                        setUnit(next);
                        setCustomAmount(picked ? Number(picked.start) : null);
                      }}
                    />
                  )}
                </>
              )}
            </>
          )}
          {context === "have" && status === "have" && (
            <ToggleRow label="Save to pantry" detail="Also adds it to your inventory" checked={save} onChange={setSave} disabled={!online} />
          )}
          {toPantry && (
            <>
              <p className={styles.label}>Where</p>
              <Segmented label="Where" options={LOCATIONS} value={location} onChange={setLocation} />
            </>
          )}
          {error !== null && (
            <p className="notice notice-danger" role="alert">
              {describeError(error)}
            </p>
          )}
          <button type="button" className={`btn btn-primary btn-block ${styles.add}`} onClick={() => void confirm()} disabled={busy || !customOk || (toPantry && !online)}>
            {busy ? "Adding…" : toPantry && context === "have" ? "Add to pantry" : "Add"}
          </button>
          {toPantry && !online && <NeedsConnection />}
        </>
      )}
    </BottomSheet>
  );
}
