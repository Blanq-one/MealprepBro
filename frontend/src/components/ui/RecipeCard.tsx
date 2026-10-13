import Link from "next/link";

import { dishIcon } from "@/lib/format/icons";

import { Emoji } from "./Emoji";
import styles from "./RecipeCard.module.css";

const BADGE_LABELS: Record<string, string> = { favorite: "Favorite", saved: "Saved", new: "New" };
// every seed recipe is a draft, so a card never says so: only the recipe page does (step 2b.6 approval, E)
const HIDDEN_BADGES = new Set(["draft"]);

/** What a card shows. Every number and line is a display string from the API (FLOW_SPEC §5.3). */
export type RecipeCardData = {
  title: string;
  dish_category: string;
  badges: readonly string[];
  numbers: readonly string[]; // "540 kcal", "41 g protein", "35 min", "$2.10"
  uses?: string | null; // "Uses: chicken thigh, spinach, onion"
  could_buy?: readonly string[]; // "Could buy: chickpeas $1.29 (Stop & Shop)"
  swaps?: readonly string[]; // "Swap: lime juice instead of lemon (you have it)" (M11)
  missing?: readonly string[]; // "Missing: lemon · buy $0.79 (Stop & Shop)": only what you'd buy
  why?: readonly string[]; // "Uses 3 of your items", "ready in 35 min"
};

export function RecipeCard({
  recipe,
  href,
  isFavorite,
  isSaved,
  onToggleFavorite,
  onToggleSaved,
}: {
  recipe: RecipeCardData;
  href: string;
  isFavorite: boolean;
  isSaved: boolean;
  onToggleFavorite?: () => void;
  onToggleSaved?: () => void;
}) {
  const icon = dishIcon(recipe.dish_category);
  return (
    <article className={`card ${styles.card}`}>
      <div className={styles.head}>
        <Emoji symbol={icon.emoji} label={icon.label} className={styles.icon} />
        <Link href={href} className={styles.title}>
          {recipe.title}
        </Link>
        {onToggleFavorite && (
          <button
            type="button"
            className={styles.toggle}
            aria-pressed={isFavorite}
            aria-label={isFavorite ? `Remove ${recipe.title} from favorites` : `Favorite ${recipe.title}`}
            onClick={onToggleFavorite}
          >
            {isFavorite ? "♥" : "♡"}
          </button>
        )}
        {onToggleSaved && (
          <button
            type="button"
            className={`${styles.toggle} ${styles.bookmark}`}
            aria-pressed={isSaved}
            aria-label={isSaved ? `Remove ${recipe.title} from saved for later` : `Save ${recipe.title} for later`}
            onClick={onToggleSaved}
          >
            🔖
          </button>
        )}
      </div>
      {recipe.badges.some((b) => !HIDDEN_BADGES.has(b)) && (
        <p className={styles.badges}>
          {recipe.badges.filter((b) => !HIDDEN_BADGES.has(b)).map((b) => (
            <span key={b} className={b === "new" ? "badge badge-herb" : "badge badge-accent"}>
              {BADGE_LABELS[b] ?? b}
            </span>
          ))}
        </p>
      )}
      {recipe.numbers.length > 0 && <p className={styles.numbers}>{recipe.numbers.join(" · ")}</p>}
      {recipe.uses && <p className={styles.line}>{recipe.uses}</p>}
      {recipe.could_buy?.map((line) => (
        <p key={line} className={styles.line}>
          {line}
        </p>
      ))}
      {recipe.swaps?.map((line) => (
        <p key={line} className={`${styles.line} ${styles.swap}`}>
          {line}
        </p>
      ))}
      {recipe.missing?.map((line) => (
        <p key={line} className={`${styles.line} ${styles.missing}`}>
          {line}
        </p>
      ))}
      {recipe.why && recipe.why.length > 0 && <p className={styles.why}>{recipe.why.join(" · ")}</p>}
    </article>
  );
}
