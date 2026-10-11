"use client";

import Link from "next/link";
import { useState } from "react";

import { BuildingSteps, clockLabel, type Stage, useCountdown } from "@/components/ui/BuildingSteps";
import { Pottle } from "@/components/ui/Pottle";
import { RecipeCard } from "@/components/ui/RecipeCard";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { ApiError } from "@/lib/api/client";
import type { CookAnswers, Problem, Suggestion } from "@/lib/api/types";
import { nextQuick } from "@/lib/cook/answers";
import { useMarks } from "@/lib/cook/marks";
import { DAILY_NOTE, type MoreState, tapMore, useMore } from "@/lib/cook/more";
import { type StageKey, STAGES, type Wait } from "@/lib/cook/stream";

import { cardData, cardHref, initialMarks } from "./cards";
import styles from "./Results.module.css";

export const FIRST_PAGE = 12;

/** Mood is a preference (M10): your mood's recipes first, then these, each under its heading. */
export const SECTIONS: readonly { key: Suggestion["section"]; title: string | null }[] = [
  { key: "match", title: null },
  { key: "more_effort", title: "A bit more effort" },
  { key: "simpler", title: "Simpler options" },
];

/** What C5 shows, from the live stream or a stored search. */
export type ResultsData = {
  searchId: number | null;
  runId: number | null;
  header: string | null;
  suggestions: Suggestion[] | null; // null until the first ranked list
  status: string; // running | succeeded | partial | failed | lost
  stage: StageKey | null;
  elapsedS: number;
  emptyReason: string | null;
  emptyFilter: string | null;
  problem: Problem | null;
  generating?: boolean; // the search is writing new ideas (step 2b.3b)
  wait?: Wait | null; // ...and waiting for the recipe service
  newIds?: number[];
  notes?: string[];
};

/** A change to the answers that the empty state offers, from the filter that removed the most recipes. */
export type Fix = { label: string; answers: CookAnswers } | { label: string; href: string } | { label: string; more: true };

export function emptyFixes(filter: string | null, answers: CookAnswers | null): Fix[] {
  const fixes: Fix[] = [];
  if (answers && filter === "time") {
    const next = nextQuick(answers.time_limit_minutes ?? null);
    const goals = answers.goals ?? [];
    const quick = goals.includes("quick") ? goals : [...goals, "quick" as const];
    if (next !== null) fixes.push({ label: `Allow ${next} min`, answers: { ...answers, goals: quick, time_limit_minutes: next } });
  }
  if (filter === "equipment") fixes.push({ label: "Check your equipment", href: "/settings/" });
  if (filter === "held" || filter === "excluded" || filter === "frequency_cap") fixes.push({ label: "Review held items", href: "/settings/" });
  fixes.push({ label: "Write new recipes", more: true });
  return fixes;
}

function stagesFor(stage: StageKey | null): Stage[] {
  const at = stage === null ? 0 : STAGES.findIndex((s) => s.key === stage);
  return STAGES.map((s, i) => ({ key: s.key, label: s.label, state: i < at ? "done" : i === at ? "current" : "pending" }));
}

function problemError(problem: Problem): ApiError {
  return new ApiError(problem.status, problem.title, problem.detail);
}

/** "Writing new ideas…", or during a rate-limit wait the friendly countdown (FLOW_SPEC §5.5). Never an error. */
export function IdeasStrip({ wait }: { wait: Wait | null }) {
  const left = useCountdown(wait?.seconds ?? null, wait?.startedAt ?? null);
  const waiting = left !== null && left > 0;
  return (
    <div className={styles.strip} role="status" aria-live="polite">
      <Pottle state="working" size={40} decorative />
      <p>{waiting ? `The recipe service needs a short breather. Writing your ideas in ${clockLabel(left)}…` : "Writing new ideas…"}</p>
    </div>
  );
}

/** More ideas (E18): the first tap waits for one ideas call; later taps show the held batch at once. "Ready in
 * 0:45" counts down a wait too long for the request; "Writing…" when tapped while the next batch is written. */
export function MoreIdeasButton({ more, searchId, disabled }: { more: MoreState | null; searchId: number; disabled: boolean }) {
  const left = useCountdown(more?.retry?.seconds ?? null, more?.retry?.startedAt ?? null);
  const cooling = left !== null && left > 0;
  const label = more?.wantMore ? "Writing…" : cooling ? `Ready in ${clockLabel(left)}` : "More ideas";
  const off = disabled || !!more?.live || !!more?.wantMore || !!more?.daily || cooling;
  return (
    <div className={styles.more}>
      <button type="button" className="btn btn-block" disabled={off} aria-busy={more?.wantMore || more?.live ? true : undefined} onClick={() => tapMore(searchId)}>
        {label}
      </button>
      {more?.daily && <p className="small muted">{DAILY_NOTE}</p>}
    </div>
  );
}

/** C5 Results for a meal now (FLOW_SPEC §7): the header with Edit, the top 12 cards (Show more for the rest),
 * new ideas streaming in with New badges, More ideas, and the loading, empty, error and lost states. */
export function ResultsView({
  data,
  answers,
  error,
  online,
  onRetry,
  onEdit,
  onRerun,
}: {
  data: ResultsData;
  answers: CookAnswers | null;
  error: unknown;
  online: boolean;
  onRetry: () => void;
  onEdit: () => void;
  onRerun: (answers: CookAnswers) => void;
}) {
  const [all, setAll] = useState(false);
  const more = useMore(data.searchId);
  const cards = more?.shown ?? data.suggestions ?? [];
  const newIds = more?.shown ? more.newIds : (data.newIds ?? []);
  const { marks, toggle, error: markError } = useMarks(initialMarks(cards), online);

  if (error) return <ErrorState error={error} onRetry={onRetry} runId={data.runId} />;
  if (data.suggestions === null) {
    if (data.status === "failed" && data.problem) return <ErrorState error={problemError(data.problem)} onRetry={onRetry} runId={data.runId} />;
    if (data.status === "lost" || data.status === "failed") {
      return <ErrorState error={null} title="Lost the connection" onRetry={onRetry} runId={data.runId} />;
    }
    return (
      <>
        <BuildingSteps stages={stagesFor(data.stage)} elapsedS={data.elapsedS} />
        <Skeleton cards={2} label="Loading recipes" />
      </>
    );
  }

  const shown = all ? cards : cards.slice(0, FIRST_PAGE);
  const done = data.status !== "running";
  const writing = (!done && !!data.generating) || !!more?.live;
  const notes = more?.shown || more?.notes.length ? (more?.notes ?? []) : (data.notes ?? []);
  const canMore = data.searchId !== null && done && data.status !== "failed" && data.status !== "lost";
  return (
    <>
      <header className={styles.header}>
        <h1 className={styles.title}>{data.header ?? "Your matches"}</h1>
        <button type="button" className="btn btn-small" onClick={onEdit}>
          Edit
        </button>
      </header>
      {writing && <IdeasStrip wait={more?.live ? more.wait : (data.wait ?? null)} />}
      {!writing && newIds.length > 0 && (
        <p className={styles.toast} role="status">
          {newIds.length === 1 ? "1 new idea added" : `${newIds.length} new ideas added`}
        </p>
      )}
      {notes
        .filter((note) => note !== DAILY_NOTE || !more?.daily)
        .map((note) => (
          <p key={note} className="notice">
            {note}
          </p>
        ))}
      {data.status === "lost" && (
        <div className="notice notice-warn" role="alert">
          <p className={styles.lost}>Lost the connection; these may be incomplete.</p>
          <button type="button" className="btn btn-small" onClick={onRetry} disabled={!online}>
            Try again
          </button>
        </div>
      )}
      {data.status === "failed" && data.problem && cards.length > 0 && (
        <p className="notice notice-warn" role="alert">
          {data.problem.title}: these may be incomplete.
        </p>
      )}
      {markError && (
        <p className="notice notice-danger" role="alert">
          {markError}
        </p>
      )}

      {done && cards.length === 0 && (
        <>
          <EmptyState message={data.emptyReason ?? "Nothing fits these answers."} />
          <div className={styles.fixes}>
            {emptyFixes(data.emptyFilter, answers).map((fix) =>
              "answers" in fix ? (
                <button key={fix.label} type="button" className="btn btn-block" disabled={!online} onClick={() => onRerun(fix.answers)}>
                  {fix.label}
                </button>
              ) : "href" in fix ? (
                <Link key={fix.label} className="btn btn-block" href={fix.href}>
                  {fix.label}
                </Link>
              ) : (
                <button
                  key={fix.label}
                  type="button"
                  className="btn btn-block"
                  disabled={!online || !canMore || !!more?.live || !!more?.daily}
                  onClick={() => data.searchId !== null && tapMore(data.searchId)}
                >
                  {fix.label}
                </button>
              ),
            )}
          </div>
        </>
      )}

      {SECTIONS.map(({ key, title }) => {
        const here = shown.filter((card) => (card.section ?? "match") === key);
        if (here.length === 0) return null;
        return (
          <section key={key} aria-label={title ?? "In your mood"} className={styles.cards}>
            {title && <h2 className={styles.section}>{title}</h2>}
            {here.map((card) => (
              <RecipeCard
                key={card.version_id}
                recipe={cardData(card)}
                href={cardHref(card, data.searchId)}
                isFavorite={marks.favorites.has(card.recipe_id)}
                isSaved={marks.saved.has(card.recipe_id)}
                onToggleFavorite={() => void toggle(card.recipe_id, "favorite", card.title)}
                onToggleSaved={() => void toggle(card.recipe_id, "saved", card.title)}
              />
            ))}
          </section>
        );
      })}
      {!all && cards.length > FIRST_PAGE && (
        <button type="button" className="btn btn-block" onClick={() => setAll(true)}>
          Show more
        </button>
      )}
      {cards.length > 0 && data.searchId !== null && <MoreIdeasButton more={more} searchId={data.searchId} disabled={!online || !canMore} />}
    </>
  );
}
