"use client";

import { useEffect, useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Segmented } from "@/components/ui/Segmented";
import { NeedsConnection } from "@/components/ui/States";
import { Stepper } from "@/components/ui/Stepper";
import { api, describeError } from "@/lib/api/client";
import type { AmountOption, BulkItemIn, InventoryLot, QuickPick, StorageLocation } from "@/lib/api/types";

import styles from "./AmountPicker.module.css";

type OptionKey = AmountOption["key"];
type Choice = OptionKey | "custom";

const OPTION_LABELS: Record<OptionKey, string> = { full: "Full", three_quarters: "¾", half: "½", quarter: "¼" };
const LOCATIONS: { value: StorageLocation; label: string }[] = [
  { value: "fridge", label: "Fridge" },
  { value: "freezer", label: "Freezer" },
  { value: "pantry", label: "Pantry" },
];
const CUSTOM_MAX = 9999;

/** The lot to add: an amount option's key, or a custom amount in one of the units the API offers. The server
 * converts it; the app never does. */
export function bulkItem(pick: QuickPick, choice: Choice, custom: { amount: number; unit: string } | null, location: StorageLocation): BulkItemIn {
  const base = { ingredient_id: pick.ingredient_id, location, expiry_is_estimate: true };
  if (choice === "custom" && custom) return { ...base, product_id: null, custom_amount: String(custom.amount), custom_unit: custom.unit };
  return { ...base, product_id: pick.product_id, amount_option: choice === "custom" ? "full" : choice };
}

/** P1 (FLOW_SPEC §9): Full, ¾, ½, ¼ or Custom, and where it goes. Default: Full. */
export function AmountPicker({
  pick,
  onClose,
  onAdded,
  online,
}: {
  pick: QuickPick | null;
  onClose: () => void;
  onAdded: (lots: InventoryLot[]) => void;
  online: boolean;
}) {
  const options = pick?.amount_options ?? [];
  const units = pick?.custom_units ?? [];
  const [choice, setChoice] = useState<Choice>("full");
  const [unit, setUnit] = useState<string>("");
  const [amount, setAmount] = useState<number | null>(null);
  const [location, setLocation] = useState<StorageLocation>("fridge");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!pick) return;
    const first = pick.custom_units?.[0];
    setChoice(pick.amount_options?.some((o) => o.key === "full") ? "full" : (pick.amount_options?.[0]?.key ?? "custom"));
    setUnit(first?.unit ?? "");
    setAmount(first ? Number(first.start) : null);
    setLocation(pick.location);
    setError(null);
  }, [pick]);

  if (!pick) return null;
  const chosenOption = options.find((o) => o.key === choice);
  const customUnit = units.find((u) => u.unit === unit);
  const step = customUnit ? Number(customUnit.step) : 1;
  const customOk = choice !== "custom" || (customUnit !== undefined && amount !== null && amount > 0);

  async function add() {
    if (!pick || !customOk) return;
    setBusy(true);
    setError(null);
    try {
      const item = bulkItem(pick, choice, amount !== null ? { amount, unit } : null, location);
      const lots = await api<InventoryLot[]>("/api/v1/inventory/bulk", { method: "POST", json: { source: "quick_add", items: [item] } });
      onAdded(lots);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet title={`${pick.name}: how much?`} open onClose={onClose}>
      <Segmented
        label="How much"
        options={[...options.map((o) => ({ value: o.key as Choice, label: OPTION_LABELS[o.key] })), ...(units.length ? [{ value: "custom" as Choice, label: "Custom" }] : [])]}
        value={choice}
        onChange={setChoice}
      />
      {chosenOption && <p className={styles.display}>{chosenOption.display}</p>}
      {choice === "custom" && customUnit && (
        <>
          <Stepper
            size="compact"
            label="Custom amount"
            value={amount}
            unit={customUnit.label}
            min={step}
            max={CUSTOM_MAX}
            step={step}
            decimal
            onChange={setAmount}
          />
          {units.length > 1 && (
            <Segmented
              label="Unit"
              options={units.map((u) => ({ value: u.unit, label: u.label }))}
              value={unit}
              onChange={(next) => {
                // each unit starts from the server's value for it: no conversion on the phone
                const picked = units.find((u) => u.unit === next);
                setUnit(next);
                setAmount(picked ? Number(picked.start) : null);
              }}
            />
          )}
        </>
      )}
      <p className={styles.where}>Where</p>
      <Segmented label="Where" options={LOCATIONS} value={location} onChange={setLocation} />
      {error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
      <button type="button" className={`btn btn-primary btn-block ${styles.add}`} onClick={() => void add()} disabled={busy || !online || !customOk}>
        {busy ? "Adding…" : "Add"}
      </button>
      {!online && <NeedsConnection />}
    </BottomSheet>
  );
}
