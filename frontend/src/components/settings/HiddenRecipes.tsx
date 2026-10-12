"use client";

// Settings, Hidden recipes (step 2b.7, F24): every recipe you marked Not for me, with Show again (the undo).
import { useState } from "react";

import { setHidden } from "@/components/cook/NotForMe";
import { Emoji } from "@/components/ui/Emoji";
import { QuestionScreen } from "@/components/ui/QuestionScreen";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { describeError } from "@/lib/api/client";
import type { HiddenRecipe } from "@/lib/api/types";
import { dishIcon } from "@/lib/format/icons";
import { useApi } from "@/lib/hooks/useApi";

import styles from "./HiddenRecipes.module.css";

const KINDS: Record<string, string> = { dish: "Recipe", prep_item: "Prep item", assembly: "Meal" };

export function HiddenRecipesEditor({ onDone, online }: { onDone: () => void; online: boolean }) {
  const list = useApi<HiddenRecipe[]>("/api/v1/recipes/hidden");
  const [busy, setBusy] = useState<number | null>(null);
  const [shown, setShown] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function showAgain(item: HiddenRecipe) {
    setBusy(item.recipe_id);
    setError(null);
    try {
      await setHidden(item.recipe_id, false);
      list.setData((list.data ?? []).filter((h) => h.recipe_id !== item.recipe_id));
      setShown(`${item.title} can come up again.`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <QuestionScreen title="Hidden recipes" why="Recipes you marked Not for me never come up in suggestions or plans. Show one again to bring it back." onBack={onDone} primaryLabel="Done" onPrimary={onDone}>
      {shown && (
        <p className="notice" role="status">
          {shown}
        </p>
      )}
      {list.loading && !list.data && <Skeleton cards={2} label="Loading your hidden recipes" />}
      {!list.data && list.error !== null && <ErrorState error={list.error} onRetry={() => void list.reload()} />}
      {list.data && list.data.length === 0 && <p className="muted">Nothing hidden. Tap Not for me on a recipe you never want suggested.</p>}
      {list.data && list.data.length > 0 && (
        <ul className={`list card ${styles.rows}`} aria-label="Hidden recipes">
          {list.data.map((item) => {
            const icon = dishIcon(item.dish_category);
            return (
              <li key={item.recipe_id} className={styles.row}>
                <Emoji symbol={icon.emoji} label={icon.label} className={styles.icon} />
                <span className={styles.text}>
                  <span className={styles.title}>{item.title}</span>
                  <span className="small muted">{KINDS[item.kind] ?? "Recipe"}</span>
                </span>
                <button type="button" className="btn btn-small" disabled={!online || busy === item.recipe_id} onClick={() => void showAgain(item)}>
                  Show again
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {!online && <p className="small muted">Showing a recipe again needs a connection.</p>}
      {error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
    </QuestionScreen>
  );
}
