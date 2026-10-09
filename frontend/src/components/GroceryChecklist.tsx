"use client";

import { type FormEvent, useState } from "react";

import type { GroceryItem, GroceryItemPatch, GroceryList } from "@/lib/api/types";
import { centsToInput, parseDollarsToCents } from "@/lib/format/money";

import styles from "./GroceryChecklist.module.css";

export const WEIGHT_UNITS = ["lb", "oz", "g", "kg", "count"] as const;

/** What the row shows right after a change, before the server's answer comes back. */
export type ItemOverride = { checked?: boolean; purchased?: string | null; actual_price_display?: string | null };

type Props = {
  list: GroceryList;
  overrides?: Record<number, ItemOverride>;
  disabled?: boolean;
  onPatch: (item: GroceryItem, changes: GroceryItemPatch) => void;
};

function Row({
  item,
  override,
  disabled,
  onPatch,
}: {
  item: GroceryItem;
  override?: ItemOverride;
  disabled?: boolean;
  onPatch: Props["onPatch"];
}) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [unit, setUnit] = useState<(typeof WEIGHT_UNITS)[number]>("lb");
  const [price, setPrice] = useState(centsToInput(item.actual_price_cents));
  const checked = override?.checked ?? item.checked;
  const purchased = override?.purchased !== undefined ? override.purchased : item.purchased;
  const paid = override?.actual_price_display !== undefined ? override.actual_price_display : item.actual_price_display;
  const cents = parseDollarsToCents(price);
  const amountOk = amount.trim() === "" || /^\d+(\.\d+)?$/.test(amount.trim());
  const checkable = item.kind !== "from_inventory";

  function save(event: FormEvent) {
    event.preventDefault();
    if (cents === undefined || !amountOk) return;
    const changes: GroceryItemPatch = { checked: true };
    if (amount.trim()) {
      changes.purchased_amount = amount.trim();
      changes.purchased_unit = unit;
    }
    if (cents !== null) changes.actual_price_cents = cents;
    onPatch(item, changes);
    setOpen(false);
  }

  return (
    <li className={checked ? `${styles.row} ${styles.checked}` : styles.row}>
      <div className={styles.main}>
        {checkable ? (
          <input
            type="checkbox"
            className={styles.box}
            checked={checked}
            disabled={disabled}
            aria-label={`Got ${item.name}`}
            onChange={(e) => onPatch(item, { checked: e.target.checked })}
          />
        ) : (
          <span className={styles.boxSpacer} aria-hidden="true" />
        )}
        <button type="button" className={styles.text} onClick={() => setOpen(!open)} aria-expanded={open} disabled={disabled}>
          <span className={styles.name}>{item.name}</span>
          <span className="small">
            {item.to_buy}
            {item.from_inventory ? ` · ${item.from_inventory} from inventory` : ""}
          </span>
          {item.note && <span className="small muted">{item.note}</span>}
          {item.expected_remainder && <span className="small muted">{item.expected_remainder}</span>}
          {(purchased || paid) && (
            <span className="small">
              Got {purchased ?? "it"}
              {paid ? ` for ${paid}` : ""}
            </span>
          )}
        </button>
        <span className={styles.cost}>{item.estimated_cost_display ?? ""}</span>
      </div>
      {open && checkable && (
        <form className={styles.details} onSubmit={save}>
          <label htmlFor={`amount-${item.id}`}>Actual weight or count (optional)</label>
          <div className="row">
            <input
              id={`amount-${item.id}`}
              inputMode="decimal"
              value={amount}
              placeholder={item.to_buy}
              onChange={(e) => setAmount(e.target.value)}
              aria-invalid={!amountOk}
            />
            <select aria-label="Unit" value={unit} onChange={(e) => setUnit(e.target.value as (typeof WEIGHT_UNITS)[number])} style={{ width: "6.5em" }}>
              {WEIGHT_UNITS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>
          <label htmlFor={`price-${item.id}`}>Price paid (optional)</label>
          <input
            id={`price-${item.id}`}
            inputMode="decimal"
            placeholder="$"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            aria-invalid={cents === undefined}
          />
          <button type="submit" className="btn btn-primary btn-block" disabled={cents === undefined || !amountOk} style={{ marginTop: 10 }}>
            Save and check off
          </button>
        </form>
      )}
    </li>
  );
}

/** The trip's list as the server grouped it: by store (or category), then stock-up, inventory, "check you
 * have" and unpriced sections. */
export function GroceryChecklist({ list, overrides = {}, disabled, onPatch }: Props) {
  return (
    <div>
      {list.note && <p className="notice">{list.note}</p>}
      {list.groups.map((group) => (
        <section key={group.key} className="card" aria-label={group.store_name}>
          <div className="row-between">
            <h2>{group.store_name}</h2>
            {group.subtotal_cents > 0 && <span className="muted">{group.subtotal_display}</span>}
          </div>
          <ul className="list">
            {group.items.map((item) => (
              <Row key={item.id} item={item} override={overrides[item.id]} disabled={disabled} onPatch={onPatch} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
