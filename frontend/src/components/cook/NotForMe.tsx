"use client";

import { useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { NeedsConnection } from "@/components/ui/States";
import { api, describeError } from "@/lib/api/client";

import styles from "./NotForMe.module.css";

/** Not for me (F24) on or off: PUT hides the recipe from every future suggestion and plan, DELETE shows it
 * again. `planMealId`: the plan meal you tapped it on (recorded with the event). */
export async function setHidden(recipeId: number, hidden: boolean, planMealId?: number | null): Promise<void> {
  const query = hidden && planMealId ? `?plan_meal=${planMealId}` : "";
  await api<void>(`/api/v1/recipes/${recipeId}/hidden${query}`, { method: hidden ? "PUT" : "DELETE" });
}

export const HIDDEN_NOTE = "Hidden: it won't be suggested or planned again. Plans you already have keep it.";

/** The control itself: "Not for me", then "Hidden … · Undo". Separate from Swap (which replaces one meal). */
export function NotForMe({ recipeId, title, hidden = false, online, planMealId = null }: { recipeId: number; title: string; hidden?: boolean; online: boolean; planMealId?: number | null }) {
  const [isHidden, setIsHidden] = useState(hidden);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function change(next: boolean) {
    setBusy(true);
    setError(null);
    try {
      await setHidden(recipeId, next, planMealId);
      setIsHidden(next);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.notForMe}>
      {isHidden ? (
        <p className={styles.hidden} role="status">
          <span>{HIDDEN_NOTE}</span>
          <button type="button" className="btn btn-link" disabled={busy || !online} onClick={() => void change(false)} aria-label={`Undo: show ${title} again`}>
            Undo
          </button>
        </p>
      ) : (
        <button type="button" className="btn btn-link" disabled={busy || !online} onClick={() => void change(true)} aria-label={`Not for me: never suggest ${title} again`}>
          Not for me
        </button>
      )}
      {!online && <NeedsConnection />}
      {error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
    </div>
  );
}

/** A plan meal row's ⋯: a sheet with Not for me for that meal's recipe (or assembly). Swap joins it in 2b.6. */
export function MealMore({ recipeId, title, online, planMealId }: { recipeId: number; title: string; online: boolean; planMealId?: number | null }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className={styles.more} aria-label={`More for ${title}`} onClick={() => setOpen(true)}>
        ⋯
      </button>
      <BottomSheet title={title} open={open} onClose={() => setOpen(false)}>
        <p className="small muted">Not for me hides it from every future suggestion and plan. This plan keeps it; show it again from Settings, Hidden recipes.</p>
        <NotForMe recipeId={recipeId} title={title} online={online} planMealId={planMealId} />
        <button type="button" className="btn btn-block" onClick={() => setOpen(false)}>
          Close
        </button>
      </BottomSheet>
    </>
  );
}
