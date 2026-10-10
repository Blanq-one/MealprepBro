"use client";

import { useState } from "react";

import { ApiError, api } from "@/lib/api/client";
import type { Cooked } from "@/lib/api/types";

import { ProblemNotice } from "./Status";

/** The big "Mark cooked" button: the server deducts the batch's quantities from inventory. */
export function MarkCooked({
  batchId,
  status,
  onCooked,
  disabled = false,
}: {
  batchId: number;
  status: string;
  onCooked?: (result: Cooked) => void;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Cooked | null>(null);
  const [error, setError] = useState<unknown>(null);
  const done = status === "cooked" || result !== null;

  async function cook() {
    setBusy(true);
    setError(null);
    try {
      const out = await api<Cooked>(`/api/v1/cook-batches/${batchId}/cooked`, { method: "POST", json: {} });
      setResult(out);
      onCooked?.(out);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const alreadyCooked = error instanceof ApiError && error.status === 409;
  return (
    <div>
      {!done && !alreadyCooked && (
        <button type="button" className="btn btn-primary btn-block" onClick={cook} disabled={busy || disabled}>
          {busy ? "Updating inventory…" : "Mark cooked"}
        </button>
      )}
      {(done || alreadyCooked) && !result && <p className="badge badge-accent">Cooked</p>}
      {alreadyCooked ? <p className="muted small">This batch was already marked cooked.</p> : <ProblemNotice error={error} />}
      {result && (
        <div className="card" role="status">
          <h3>Cooked: inventory updated</h3>
          <ul className="list small">
            {result.deductions.map((d) => (
              <li key={d.ingredient_id}>
                {d.name}: used {d.taken}
                {d.shortfall && <span className="badge badge-warn"> {d.shortfall} not in inventory</span>}
              </li>
            ))}
          </ul>
          {result.open_packages.length > 0 && (
            <>
              <h3>Open packages left</h3>
              <ul className="list small">
                {result.open_packages.map((lot) => (
                  <li key={lot.id}>
                    {lot.name}: {lot.display} ({lot.location}
                    {lot.expires_on ? `, use by ${lot.expires_on}` : ""})
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
