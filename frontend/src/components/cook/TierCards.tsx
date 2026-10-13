"use client";

// The shopping step's budget tiers (step 2b.6, AA6): Cheapest, A bit better and Fancy for this week, each with
// its estimated total and protein per day (a quick solve on the server, so they say "about"). Tapping one picks
// it; the full plan is solved when you build it. Every number and line is the server's.
import { useEffect, useState } from "react";

import { Pottle } from "@/components/ui/Pottle";
import { api, describeError } from "@/lib/api/client";
import type { CookAnswers, PriceTier, TierCard } from "@/lib/api/types";

import styles from "./TierCards.module.css";

export function fetchTierCards(answers: CookAnswers): Promise<TierCard[]> {
  return api<TierCard[]>("/api/v1/cook/meal-prep/tiers", { method: "POST", json: { ...answers, shopping: "make_a_list", budget_cents: null, price_tier: null } });
}

export function TierCards({ answers, selected, online, onPick }: { answers: CookAnswers; selected: PriceTier | null; online: boolean; onPick: (tier: PriceTier) => void }) {
  const key = JSON.stringify({ ...answers, price_tier: null, budget_cents: null });
  const [cards, setCards] = useState<TierCard[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!online) return;
    let live = true;
    setCards(null);
    setError(null);
    fetchTierCards(JSON.parse(key) as CookAnswers)
      .then((c) => live && setCards(c))
      .catch((e: unknown) => live && setError(e));
    return () => {
      live = false;
    };
  }, [key, online]);

  if (!online) return <p className="small muted">The tiers need a connection.</p>;
  if (error !== null)
    return (
      <p className="notice notice-danger" role="alert">
        {describeError(error)}
      </p>
    );
  if (!cards)
    return (
      <div className={styles.working} role="status">
        <Pottle state="working" size={40} decorative />
        <p>Pricing three ways to shop this week…</p>
      </div>
    );
  return (
    <ul className={styles.cards} aria-label="Budget tiers">
      {cards.map((card) => {
        const on = selected === card.tier;
        const fits = card.status === "estimated";
        return (
          <li key={card.tier}>
            <button type="button" className={on ? `${styles.card} ${styles.on}` : styles.card} aria-pressed={on} disabled={!fits} onClick={() => onPick(card.tier)}>
              <span className={styles.head}>
                <span className={styles.label}>
                  {on && <span aria-hidden="true">✓ </span>}
                  {card.label}
                </span>
                {fits && <span className={styles.total}>{card.total_display}</span>}
              </span>
              {fits ? <span className={styles.protein}>{card.protein_per_day_display}</span> : <span className={styles.protein}>{card.reason}</span>}
              <span className={styles.blurb}>{card.blurb}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
