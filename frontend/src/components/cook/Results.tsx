"use client";

import Link from "next/link";
import { useState } from "react";

import { BuildingSteps, type Stage } from "@/components/ui/BuildingSteps";
import { RecipeCard } from "@/components/ui/RecipeCard";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { ApiError } from "@/lib/api/client";
import type { CookAnswers, Problem, Suggestion } from "@/lib/api/types";
import { nextQuick } from "@/lib/cook/answers";
import { useMarks } from "@/lib/cook/marks";
import { type StageKey, STAGES } from "@/lib/cook/stream";

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
};

/** A change to the answers that the empty state offers, from the filter that removed the most recipes. */
export type Fix = { label: string; answers: CookAnswers } | { label: string; href: string } | { label: string; disabled: true };

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
  fixes.push({ label: "Write new recipes (coming soon)", disabled: true });
  return fixes;
}

function stagesFor(stage: StageKey | null): Stage[] {
  const at = stage === null ? 0 : STAGES.findIndex((s) => s.key === stage);
  return STAGES.map((s, i) => ({ key: s.key, label: s.label, state: i < at ? "done" : i === at ? "current" : "pending" }));
}

function problemError(problem: Problem): ApiError {
  return new ApiError(problem.status, problem.title, problem.detail);
}

/** C5 Results for a meal now (FLOW_SPEC §7): the header with Edit, the top 12 cards (Show more for the rest),
 * More ideas (disabled, "coming soon", until step 2b.3b), and the loading, empty, error and lost states. */
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
  const cards = data.suggestions ?? [];
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
  return (
    <>
      <header className={styles.header}>
        <h1 className={styles.title}>{data.header ?? "Your matches"}</h1>
        <button type="button" className="btn btn-small" onClick={onEdit}>
          Edit
        </button>
      </header>
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
                <button key={fix.label} type="button" className="btn btn-block" disabled>
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
      {cards.length > 0 && (
        <div className={styles.more}>
          <button type="button" className="btn btn-block" disabled aria-describedby="more-ideas-soon">
            More ideas
          </button>
          <p id="more-ideas-soon" className="small muted">
            New recipe ideas: coming soon.
          </p>
        </div>
      )}
    </>
  );
}
