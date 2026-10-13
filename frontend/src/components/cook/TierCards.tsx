"use client";

// The shopping step's budget tiers (step 2b.6, AA6; four since its approval): Broke mode, Cheapest, A bit better
// and Fancy for this week, each with its estimated regular groceries, the stock-up items apart, its protein (for
// some of your meals, their share of your day's target) and what it includes. A quick solve on the server, so
// they say "about". Since the deploy (AC3–AC6): the cards stream in one by one (Broke mode first); a card that
// costs about the same as the priciest one below says "Same as Cheapest this week", and one that costs less says
// so with its real price and why (AD1: a saving is never hidden); one whose upgrades fall short says why, with
// its fix as a button; a week that can't be planned says why, with "Start tomorrow" and "Cook on Tuesday too"; one that ran out of time (or a slow database) says "Taking longer than usual" with
// Try again, still pickable; and the cards for the same answers come back at once when you reopen the step
// (this page keeps them a few minutes; the server keeps them too). Tapping one picks it; the full plan is solved
// when you build it. Every number and line is the server's.
import { useEffect, useState } from "react";

import { Pottle } from "@/components/ui/Pottle";
import { ApiError, describeError } from "@/lib/api/client";
import type { CookAnswers, PriceTier, TierCard, TierFix, TierStreamEvent } from "@/lib/api/types";
import { streamLines } from "@/lib/cook/stream";

import styles from "./TierCards.module.css";

export const SLOW_TITLE = "Taking longer than usual";
const TIERS: PriceTier[] = ["broke", "cheapest", "better", "fancy"];
const KEEP_MS = 10 * 60 * 1000; // reopening the step within this shows the last cards at once
const kept = new Map<string, { cards: TierCard[]; at: number }>();

/** The request the cards are priced for: a shopping list with no tier or limit of its own. */
export function tierRequest(answers: CookAnswers): CookAnswers {
  return { ...answers, shopping: "make_a_list", budget_cents: null, price_tier: null };
}

export function streamTierCards(answers: CookAnswers, onEvent: (event: TierStreamEvent) => void, signal?: AbortSignal): Promise<void> {
  return streamLines<TierStreamEvent>("/api/v1/cook/meal-prep/tiers", tierRequest(answers), onEvent, signal);
}

/** The cards this page priced for the same request in the last few minutes (all of them, none out of time). */
export function keptCards(key: string, now: number = Date.now()): TierCard[] | null {
  const hit = kept.get(key);
  return hit && now - hit.at < KEEP_MS ? hit.cards : null;
}

export function forgetTierCards(): void {
  kept.clear();
}

/** A failure that is the server being slow (a cold start, a timeout, a dropped connection): try again. */
export function isSlow(error: unknown): boolean {
  if (error instanceof TypeError) return true;
  if (!(error instanceof ApiError)) return false;
  return error.status === 502 || error.status === 503 || error.status === 504 || error.body?.code === "db_unavailable";
}

type Status = "loading" | "done" | "slow" | "failed";

function SlowNotice({ onRetry }: { onRetry: () => void }) {
  return (
    <div className={styles.slow} role="status">
      <Pottle state="working" size={40} decorative />
      <div>
        <p className={styles.slowTitle}>{SLOW_TITLE}</p>
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      </div>
    </div>
  );
}

export function TierCards({
  answers,
  selected,
  online,
  onPick,
  onFix,
}: {
  answers: CookAnswers;
  selected: PriceTier | null;
  online: boolean;
  onPick: (tier: PriceTier) => void;
  onFix?: (fix: TierFix) => void;
}) {
  const key = JSON.stringify(tierRequest(answers));
  const [cards, setCards] = useState<TierCard[]>(() => keptCards(key) ?? []);
  const [status, setStatus] = useState<Status>(() => (keptCards(key) ? "done" : "loading"));
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!online) return;
    const again = keptCards(key);
    if (again && attempt === 0) {
      setCards(again);
      setStatus("done");
      return;
    }
    const controller = new AbortController();
    let ended = false;
    setCards([]);
    setStatus("loading");
    setError(null);
    streamTierCards(
      JSON.parse(key) as CookAnswers,
      (event) => {
        if (event.event === "card" && event.card) {
          const card = event.card;
          setCards((now) => [...now.filter((c) => c.tier !== card.tier), card]);
        }
        if (event.event !== "result") return;
        ended = true;
        if (event.status === "failed") {
          const code = event.problem?.code;
          setError(event.problem ? new ApiError(event.problem.status ?? 500, event.problem.title ?? "Request failed", event.problem.detail ?? "", [], null, [], { code }) : null);
          setStatus(code === "db_unavailable" || code === undefined ? "slow" : "failed");
          return;
        }
        setCards(event.cards ?? []);
        setStatus("done");
        if ((event.cards ?? []).every((c) => c.status !== "timed_out")) kept.set(key, { cards: event.cards ?? [], at: Date.now() });
      },
      controller.signal,
    )
      .then(() => {
        if (!ended && !controller.signal.aborted) setStatus("slow"); // the connection dropped before the end
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e);
        setStatus(isSlow(e) ? "slow" : "failed");
      });
    return () => controller.abort();
  }, [key, online, attempt]);

  const retry = () => {
    kept.delete(key);
    setAttempt((n) => n + 1);
  };

  if (!online) return <p className="small muted">The tiers need a connection.</p>;
  if (status === "failed")
    return (
      <div className={styles.failed}>
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
        <button type="button" className="btn" onClick={retry}>
          Try again
        </button>
      </div>
    );
  const byTier = new Map(cards.map((c) => [c.tier, c]));
  const shown = TIERS.map((t) => byTier.get(t)).filter((c): c is TierCard => c !== undefined);
  return (
    <>
      {shown.length > 0 && (
        <ul className={styles.cards} aria-label="Budget tiers">
          {shown.map((card) => {
            const on = selected === card.tier;
            const fits = card.status === "estimated";
            const slow = card.status === "timed_out";
            const pickable = fits || slow;
            return (
              <li key={card.tier}>
                <button type="button" className={on ? `${styles.card} ${styles.on}` : styles.card} aria-pressed={on} disabled={!pickable} onClick={() => onPick(card.tier)}>
                  <span className={styles.head}>
                    <span className={styles.label}>
                      {on && <span aria-hidden="true">✓ </span>}
                      {card.label}
                    </span>
                    {fits && card.same_as_display && <span className={styles.total}>{card.same_as_display}</span>}
                    {fits && !card.same_as_display && (
                      <span className={styles.total}>
                        {card.total_display} <span className={styles.unit}>groceries</span>
                      </span>
                    )}
                  </span>
                  {fits && card.less_than_display && <span className={styles.less}>{card.less_than_display}</span>}
                  {fits && card.stock_up_display && <span className={styles.stock}>{card.stock_up_display}</span>}
                  {fits ? <span className={styles.protein}>{card.protein_per_day_display}</span> : <span className={slow ? styles.slowTitle : styles.protein}>{card.reason}</span>}
                  {fits && card.includes_display && <span className={styles.includes}>{card.includes_display}</span>}
                  {fits && card.shortfall_display && <span className={styles.shortfall}>{card.shortfall_display}</span>}
                  <span className={styles.blurb}>{card.blurb}</span>
                </button>
                {((card.fixes ?? []).length > 0 || slow) && (
                  <div className={styles.after}>
                    {onFix &&
                      (card.fixes ?? []).map((fix) => (
                        <button key={`${fix.kind}-${fix.day}`} type="button" className="btn" onClick={() => onFix(fix)}>
                          {fix.label}
                        </button>
                      ))}
                    {slow && (
                      <button type="button" className="btn" onClick={retry}>
                        Try again
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {status === "loading" && (
        <div className={styles.working} role="status">
          <Pottle state="working" size={40} decorative />
          <p>{shown.length === 0 ? "Pricing four ways to shop this week…" : "Pricing the next one…"}</p>
        </div>
      )}
      {status === "slow" && shown.length < TIERS.length && <SlowNotice onRetry={retry} />}
    </>
  );
}
