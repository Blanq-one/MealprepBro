// ♥ favorites and 🔖 save for later (E7, E8): optimistic on screen, queued while offline and replayed once
// (PUT and DELETE are idempotent on the server, so a replay never logs a second change).
import { useCallback, useEffect, useState } from "react";

import { appQueue, type OfflineQueue } from "@/lib/offline/queue";

export type MarkKind = "favorite" | "saved";

export function markUrl(recipeId: number, kind: MarkKind): string {
  return `/api/v1/recipes/${recipeId}/${kind}`;
}

/** Send the change now, or queue it when there's no connection. Returns "sent" | "queued". */
export async function sendMark(
  recipeId: number,
  kind: MarkKind,
  on: boolean,
  title: string,
  { online, queue = appQueue() }: { online: boolean; queue?: OfflineQueue },
): Promise<"sent" | "queued"> {
  const method = on ? "PUT" : "DELETE";
  const label = `${on ? "" : "Un-"}${kind === "favorite" ? "favorite" : "save"} ${title}`;
  if (online) {
    try {
      const response = await fetch(markUrl(recipeId, kind), { method, credentials: "same-origin" });
      if (response.ok) return "sent";
      if (response.status >= 400 && response.status < 500 && response.status !== 401) {
        throw new Error(`${label}: the server said no (${response.status})`);
      }
    } catch (error) {
      if (!(error instanceof TypeError)) throw error; // offline after all: queue it below
    }
  }
  queue.enqueue({ method, url: markUrl(recipeId, kind), label });
  return "queued";
}

export type Marks = { favorites: Set<number>; saved: Set<number> };

/** Local, optimistic marks for a screen, starting from the server's badges. */
export function useMarks(initial: { favorites: number[]; saved: number[] }, online: boolean) {
  const key = `${initial.favorites.join(",")}|${initial.saved.join(",")}`;
  const [marks, setMarks] = useState<Marks>(() => ({ favorites: new Set(initial.favorites), saved: new Set(initial.saved) }));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setMarks({ favorites: new Set(initial.favorites), saved: new Set(initial.saved) });
    // reset only when the server's list changes (the key stands for both lists)
  }, [key]);

  const toggle = useCallback(
    async (recipeId: number, kind: MarkKind, title: string) => {
      const set = kind === "favorite" ? "favorites" : "saved";
      const on = !marks[set].has(recipeId);
      const flip = (to: boolean) =>
        setMarks((m) => {
          const copy = new Set(m[set]);
          if (to) copy.add(recipeId);
          else copy.delete(recipeId);
          return { ...m, [set]: copy };
        });
      flip(on);
      setError(null);
      try {
        await sendMark(recipeId, kind, on, title, { online });
      } catch (e) {
        flip(!on);
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [marks, online],
  );
  return { marks, toggle, error };
}
