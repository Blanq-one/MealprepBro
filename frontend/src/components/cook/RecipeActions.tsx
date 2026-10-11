"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { NeedsConnection } from "@/components/ui/States";
import { api, describeError } from "@/lib/api/client";
import type { CookMealIn, CookMealOut } from "@/lib/api/types";
import { useMarks } from "@/lib/cook/marks";

import styles from "./RecipeActions.module.css";

/** Where Cook this goes next: the Buy first checklist when something is to buy or check, else cooking mode. */
export function afterCookThis(out: Pick<CookMealOut, "batch_id" | "plan_id" | "buy_first">): string {
  return out.buy_first ? `/cook/buy/?batch=${out.batch_id}&plan=${out.plan_id}` : `/cook/cooking/?batch=${out.batch_id}`;
}

/** The sticky action bar on the recipe page (C8): Cook this (primary) · ♥ · 🔖. For a meal-now or saved
 * recipe, Cook this saves a one-meal plan for today (E3); for a plan batch it opens cooking mode. */
export function RecipeActions({
  recipe,
  cook,
  online,
  blocked = null,
}: {
  recipe: { recipe_id: number; title: string; is_favorite: boolean; is_saved: boolean };
  cook: { meal: CookMealIn } | { batchId: number };
  online: boolean;
  /** Cook this waits for something first, with this label (a new idea: "Writing steps…" until they land). */
  blocked?: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const { marks, toggle, error: markError } = useMarks(
    { favorites: recipe.is_favorite ? [recipe.recipe_id] : [], saved: recipe.is_saved ? [recipe.recipe_id] : [] },
    online,
  );
  const favorite = marks.favorites.has(recipe.recipe_id);
  const saved = marks.saved.has(recipe.recipe_id);

  async function cookThis() {
    if ("batchId" in cook) {
      router.push(`/cook/cooking/?batch=${cook.batchId}`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const out = await api<CookMealOut>("/api/v1/cook/meals", { method: "POST", json: cook.meal });
      router.push(afterCookThis(out));
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  return (
    <div className={styles.bar} role="group" aria-label="Recipe actions">
      {(error !== null || markError) && (
        <p className="notice notice-danger" role="alert">
          {error !== null ? describeError(error) : markError}
        </p>
      )}
      <div className={styles.buttons}>
        <button
          type="button"
          className={`btn btn-primary ${styles.cook}`}
          onClick={() => void cookThis()}
          disabled={busy || blocked !== null || (!online && !("batchId" in cook))}
        >
          {busy ? "Saving…" : (blocked ?? "Cook this")}
        </button>
        <button
          type="button"
          className={styles.toggle}
          aria-pressed={favorite}
          aria-label={favorite ? `Remove ${recipe.title} from favorites` : `Favorite ${recipe.title}`}
          onClick={() => void toggle(recipe.recipe_id, "favorite", recipe.title)}
        >
          {favorite ? "♥" : "♡"}
        </button>
        <button
          type="button"
          className={styles.toggle}
          aria-pressed={saved}
          aria-label={saved ? `Remove ${recipe.title} from saved for later` : `Save ${recipe.title} for later`}
          onClick={() => void toggle(recipe.recipe_id, "saved", recipe.title)}
        >
          🔖
        </button>
      </div>
      {!online && !("batchId" in cook) && <NeedsConnection />}
    </div>
  );
}
