// A search suggestion or a Saved-list card → what the recipe card shows. Only the server's strings, joined
// into lines: no number is made here (FLOW_SPEC §5.3).
import type { RecipeCardData } from "@/components/ui/RecipeCard";
import type { SavedRecipe, Suggestion } from "@/lib/api/types";

export function cardData(card: Suggestion | SavedRecipe): RecipeCardData {
  return {
    title: card.title,
    dish_category: card.dish_category,
    badges: card.badges,
    numbers: card.numbers,
    uses: card.uses.length > 0 ? `Uses: ${card.uses.join(", ")}` : null,
    could_buy: card.could_buy.map((line) => `Could buy: ${line.display}`),
    swaps: (card.swaps ?? []).map((line) => line.display), // "Swap: … (you have it)", never "Missing" (M11)
    missing: card.missing.map((line) => `Missing: ${line.display}`),
    why: "why" in card ? card.why : [],
  };
}

/** The recipe page for a card: in its search's context, or saved (at the card's portions). */
export function cardHref(card: { version_id: number; portions: number; portion_size: string }, searchId: number | null): string {
  if (searchId !== null) return `/recipe/?version=${card.version_id}&search=${searchId}`;
  return `/recipe/?version=${card.version_id}&portions=${card.portions}&size=${card.portion_size}`;
}

/** The ♥ / 🔖 marks the cards start with, from their badges. */
export function initialMarks(cards: readonly { recipe_id: number; badges: readonly string[] }[]): { favorites: number[]; saved: number[] } {
  return {
    favorites: cards.filter((c) => c.badges.includes("favorite")).map((c) => c.recipe_id),
    saved: cards.filter((c) => c.badges.includes("saved")).map((c) => c.recipe_id),
  };
}
