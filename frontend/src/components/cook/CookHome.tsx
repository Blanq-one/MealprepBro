"use client";

import Link from "next/link";

import { Emoji } from "@/components/ui/Emoji";
import { Pottle } from "@/components/ui/Pottle";
import { NeedsConnection, Skeleton } from "@/components/ui/States";
import type { CookHome as CookHomeData, LastSearch, SavedPreview } from "@/lib/api/types";
import { dishIcon, MODE_ICONS } from "@/lib/format/icons";

import styles from "./CookHome.module.css";
import { TodayCard } from "./TodayCard";

/** Where "A meal now" starts: C2 Goals, pre-filled from your last meal-now answers. */
export const MEAL_NOW_HREF = "/cook/ask/?mode=now&step=goals&fresh=1";
/** Where "Meal prep" starts: C1 How much, pre-filled from your last meal-prep answers (step 2b.7). */
export const MEAL_PREP_HREF = "/cook/ask/?mode=prep&step=amount&fresh=1";

function Choice({ href, mode, hint, online }: { href: string; mode: "now" | "prep"; hint: string; online: boolean }) {
  const icon = MODE_ICONS[mode];
  const body = (
    <>
      <span className={styles.choiceIcon} aria-hidden="true">
        {icon.emoji}
      </span>
      <span>
        <span className={styles.choiceTitle}>{icon.label}</span>
        <span className={styles.choiceHint}>{hint}</span>
      </span>
    </>
  );
  if (!online) {
    return (
      <button type="button" className={styles.choice} disabled>
        {body}
      </button>
    );
  }
  return (
    <Link href={href} className={styles.choice}>
      {body}
    </Link>
  );
}

function SavedRow({ title, icon, items, count, list, portions, size }: { title: string; icon: string; items: SavedPreview[]; count: number; list: "favorites" | "later"; portions: number; size: string }) {
  return (
    <div className={styles.savedRow}>
      <div className={styles.savedHead}>
        <h3 className={styles.savedTitle}>
          <span aria-hidden="true">{icon} </span>
          {title} <span className="muted small">{count}</span>
        </h3>
        {count > 0 && (
          <Link href={`/cook/saved/?list=${list}`} className={styles.seeAll}>
            See all
          </Link>
        )}
      </div>
      {items.length > 0 ? (
        <ul className={styles.previews} aria-label={title}>
          {items.map((item) => {
            const dish = dishIcon(item.dish_category);
            return (
              <li key={item.recipe_id}>
                <Link href={`/recipe/?version=${item.version_id}&portions=${portions}&size=${size}`} className={styles.preview}>
                  <Emoji symbol={dish.emoji} label={dish.label} className={styles.previewIcon} />
                  <span className={styles.previewTitle}>{item.title}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="small muted">{list === "favorites" ? "Nothing here yet." : "Nothing saved for later yet."}</p>
      )}
    </div>
  );
}

/** C0 Cook home: the one-line greeting, the two choice buttons (nothing else above them), then Same as last
 * time, Today and Saved. Offline, the choices and Same as last time need a connection; an error loading the
 * home leaves the choices working. */
export function CookHomeView({
  greeting,
  home,
  loading,
  error,
  online,
  onRetry,
  onSameAgain,
}: {
  greeting: string;
  home: CookHomeData | null;
  loading: boolean;
  error: unknown;
  online: boolean;
  onRetry: () => void;
  onSameAgain: (last: LastSearch) => void;
}) {
  // one per mode, most recent first ("What should I buy?" keeps its own in 2b.8)
  const again = (home?.last ?? []).filter((l) => l.mode === "now" || l.mode === "prep").slice(0, 2);
  const nothingSaved = home !== null && home.favorites_count === 0 && home.later_count === 0;
  return (
    <>
      <header className={styles.greeting}>
        <Pottle state="idle" size={32} />
        <h1 className={styles.title}>{greeting}! What are we making?</h1>
      </header>
      <section className={styles.choices} aria-label="Start cooking" data-testid="choices">
        <Choice href={MEAL_NOW_HREF} mode="now" hint="One meal, ready to cook" online={online} />
        <Choice href={MEAL_PREP_HREF} mode="prep" hint="Portions for the days ahead" online={online} />
        {!online && <NeedsConnection />}
      </section>

      {loading && !home && <Skeleton cards={2} label="Loading your Cook home" />}
      {!loading && !home && error !== null && (
        <section className="card" aria-label="Couldn't load">
          <p>Couldn&apos;t load your recent searches, today and saved recipes.</p>
          <button type="button" className="btn btn-block" onClick={onRetry}>
            Try again
          </button>
        </section>
      )}

      {again.length > 0 && (
        <section aria-label="Same as last time" className={styles.section}>
          <h2 className={styles.sectionTitle}>Same as last time</h2>
          {again.map((last) => (
            <button key={last.search_id} type="button" className={`card ${styles.again}`} disabled={!online} onClick={() => onSameAgain(last)}>
              {last.summary}
            </button>
          ))}
        </section>
      )}

      {home?.today && <TodayCard today={home.today} />}

      {home && (
        <section className={`card ${styles.section}`} aria-label="Saved">
          <h2 className={styles.sectionTitle}>Saved</h2>
          <SavedRow title="Favorites" icon="♥" items={home.favorites} count={home.favorites_count} list="favorites" portions={home.portions ?? 1} size={home.portion_size ?? "normal"} />
          <SavedRow title="Saved for later" icon="🔖" items={home.later} count={home.later_count} list="later" portions={home.portions ?? 1} size={home.portion_size ?? "normal"} />
          {nothingSaved && <p className="small muted">Tap ♥ on a recipe to keep it here.</p>}
        </section>
      )}
    </>
  );
}
