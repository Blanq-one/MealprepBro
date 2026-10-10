"use client";

import { useState } from "react";

import type { ItemOverride } from "@/components/GroceryChecklist";
import { api } from "@/lib/api/client";
import type { GroceryComplete, GroceryItem, GroceryItemPatch, GroceryList } from "@/lib/api/types";
import type { ApiState } from "@/lib/hooks/useApi";
import { appQueue } from "@/lib/offline/queue";

/** Check-offs (queued, so they work offline and replay once) and Done shopping, for the Grocery tab and the
 * Buy first checklist. */
export function useGroceryChecks(list: ApiState<GroceryList>) {
  const [overrides, setOverrides] = useState<Record<number, ItemOverride>>({});
  const [completing, setCompleting] = useState(false);
  const [completed, setCompleted] = useState<GroceryComplete | null>(null);
  const [error, setError] = useState<unknown>(null);

  function patch(item: GroceryItem, changes: GroceryItemPatch) {
    setOverrides((o) => ({
      ...o,
      [item.id]: {
        ...o[item.id],
        ...(changes.checked !== undefined ? { checked: changes.checked ?? false } : {}),
        ...(changes.purchased_amount ? { purchased: `${changes.purchased_amount} ${changes.purchased_unit ?? ""}`.trim() } : {}),
      },
    }));
    const queue = appQueue();
    queue.enqueue({
      method: "PATCH",
      url: `/api/v1/grocery-items/${item.id}`,
      body: changes as Record<string, unknown>,
      label: `${changes.checked === false ? "Uncheck" : "Check off"} ${item.name}`,
    });
    void queue.replay().then((result) => {
      if (result.sent > 0 && result.kept === 0) void list.reload().then(() => setOverrides({}));
    });
  }

  async function done(): Promise<GroceryComplete | null> {
    if (!list.data) return null;
    setCompleting(true);
    setError(null);
    try {
      const pending = await appQueue().replay();
      if (pending.kept > 0) throw new Error("Some check-offs haven't synced yet. Try again when you're online.");
      const out = await api<GroceryComplete>(`/api/v1/grocery-lists/${list.data.id}/complete`, { method: "POST", json: {} });
      setCompleted(out);
      await list.reload();
      return out;
    } catch (e) {
      setError(e);
      return null;
    } finally {
      setCompleting(false);
    }
  }

  return { overrides, patch, done, completing, completed, error };
}
