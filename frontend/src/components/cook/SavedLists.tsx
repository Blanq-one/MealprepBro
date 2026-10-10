"use client";

import { useEffect, useState } from "react";

import { useOnline } from "@/components/AppShell";
import { SyncNote } from "@/components/Status";
import { RecipeCard } from "@/components/ui/RecipeCard";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import type { SavedRecipe } from "@/lib/api/types";
import { type MarkKind, sendMark } from "@/lib/cook/marks";
import { useApi } from "@/lib/hooks/useApi";

import { cardData, cardHref } from "./cards";

export type SavedList = "favorites" | "later";

const EMPTY: Record<SavedList, string> = {
  favorites: "Nothing saved yet. Tap ♥ on a recipe you'd make again.",
  later: "Tap 🔖 on anything you want to try later.",
};

/** C7 Saved lists (FLOW_SPEC §7): ♥ Favorites | 🔖 Saved for later. Tapping a card's ♥ (or 🔖) takes it off
 * this list with Undo; the other mark toggles in place. */
export function SavedLists({ list, onList }: { list: SavedList; onList: (list: SavedList) => void }) {
  const online = useOnline();
  const cards = useApi<SavedRecipe[]>(`/api/v1/recipes/saved?list=${list}`);
  const [removed, setRemoved] = useState<SavedRecipe | null>(null);
  const [hidden, setHidden] = useState<Set<number>>(new Set());
  const [other, setOther] = useState<Record<number, boolean>>({}); // the other list's mark, changed here
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setHidden(new Set());
    setOther({});
    setRemoved(null);
  }, [list]);

  const own: MarkKind = list === "favorites" ? "favorite" : "saved";
  const otherKind: MarkKind = list === "favorites" ? "saved" : "favorite";
  const otherBadge = list === "favorites" ? "saved" : "favorite";

  async function mark(card: SavedRecipe, kind: MarkKind, on: boolean, revert: () => void) {
    setError(null);
    try {
      await sendMark(card.recipe_id, kind, on, card.title, { online });
    } catch (e) {
      revert();
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function remove(card: SavedRecipe) {
    setHidden((h) => new Set(h).add(card.recipe_id));
    setRemoved(card);
    void mark(card, own, false, () => setHidden((h) => new Set([...h].filter((id) => id !== card.recipe_id))));
  }

  function undo() {
    if (!removed) return;
    const card = removed;
    setRemoved(null);
    setHidden((h) => new Set([...h].filter((id) => id !== card.recipe_id)));
    void mark(card, own, true, () => setHidden((h) => new Set(h).add(card.recipe_id)));
  }

  function toggleOther(card: SavedRecipe) {
    const now = other[card.recipe_id] ?? card.badges.includes(otherBadge);
    setOther((o) => ({ ...o, [card.recipe_id]: !now }));
    void mark(card, otherKind, !now, () => setOther((o) => ({ ...o, [card.recipe_id]: now })));
  }

  const shown = (cards.data ?? []).filter((c) => !hidden.has(c.recipe_id));
  return (
    <>
      <h1>Saved</h1>
      <Segmented
        label="Saved lists"
        options={[
          { value: "favorites" as const, label: "♥ Favorites" },
          { value: "later" as const, label: "🔖 Saved for later" },
        ]}
        value={list}
        onChange={onList}
      />
      <SyncNote syncedAt={cards.syncedAt} fromCache={cards.fromCache} />
      {removed && (
        <div className="notice row-between" role="status">
          <span>
            Removed {removed.title} from {list === "favorites" ? "favorites" : "saved for later"}.
          </span>
          <button type="button" className="btn btn-small" onClick={undo}>
            Undo
          </button>
        </div>
      )}
      {error && (
        <p className="notice notice-danger" role="alert">
          {error}
        </p>
      )}
      {cards.loading && !cards.data && <Skeleton cards={3} label="Loading saved recipes" />}
      {!cards.loading && !cards.data && <ErrorState error={cards.error} onRetry={() => void cards.reload()} />}
      {cards.data && shown.length === 0 && !removed && <EmptyState message={EMPTY[list]} action={{ label: "Find a meal now", href: "/cook/ask/?mode=now&step=goals&fresh=1" }} />}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
        {shown.map((card) => {
          const otherOn = other[card.recipe_id] ?? card.badges.includes(otherBadge);
          return (
            <RecipeCard
              key={card.recipe_id}
              recipe={cardData(card)}
              href={cardHref(card, null)}
              isFavorite={list === "favorites" ? true : otherOn}
              isSaved={list === "later" ? true : otherOn}
              onToggleFavorite={() => (list === "favorites" ? remove(card) : toggleOther(card))}
              onToggleSaved={() => (list === "later" ? remove(card) : toggleOther(card))}
            />
          );
        })}
      </div>
    </>
  );
}
