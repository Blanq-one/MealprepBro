"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useOnline } from "@/components/AppShell";
import { type ResultsData, ResultsView } from "@/components/cook/Results";
import { Page } from "@/components/Page";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import type { CookAnswers, CookSearch } from "@/lib/api/types";
import { loadDraft, loadPending, saveDraft, savePending } from "@/lib/cook/answers";
import { liveRun, startRun, useLiveRun } from "@/lib/cook/liveRun";
import type { MealNowState } from "@/lib/cook/stream";
import { useApi } from "@/lib/hooks/useApi";

const EDIT_HREF = "/cook/ask/?mode=now&step=goals";

function fromState(state: MealNowState): ResultsData {
  return { ...state };
}

function fromSearch(search: CookSearch): ResultsData {
  return {
    searchId: search.search_id,
    runId: null,
    header: search.header,
    suggestions: search.suggestions,
    status: search.status,
    stage: "candidates",
    elapsedS: 0,
    emptyReason: search.empty_reason,
    emptyFilter: search.empty_filter,
    problem: null,
  };
}

/** Send changed answers again (an empty state's fix): the draft follows, so Edit shows them. */
function useRerun() {
  const router = useRouter();
  return (answers: CookAnswers) => {
    const draft = loadDraft();
    if (draft) saveDraft({ ...draft, mood: answers.mood ?? null, quickMinutes: answers.time_limit_minutes ?? null, goals: draft.goals.includes("quick") || !answers.time_limit_minutes ? draft.goals : [...draft.goals, "quick"] });
    router.push(`/cook/results/?run=${savePending(answers)}`);
  };
}

/** `?run=<key>`: the search you just asked for, streamed. Once it ends, the URL becomes `?search=<id>`. */
function LiveResults({ run }: { run: string }) {
  const router = useRouter();
  const online = useOnline();
  const rerun = useRerun();
  const [answers] = useState<CookAnswers | null>(() => loadPending(run));
  const live = useLiveRun(run);

  useEffect(() => {
    if (answers) startRun(run, answers);
  }, [run, answers]);

  const state = live?.state;
  useEffect(() => {
    if (state && state.searchId !== null && state.status !== "running" && state.status !== "lost") {
      router.replace(`/cook/results/?search=${state.searchId}`);
    }
  }, [state, router]);

  if (!answers) return <EmptyState message="Nothing to search for yet." action={{ label: "A meal now", href: EDIT_HREF }} />;
  if (!live) return <Skeleton cards={2} label="Finding recipes" />;
  return (
    <ResultsView
      data={fromState(live.state)}
      answers={answers}
      error={live.error}
      online={online}
      onRetry={() => rerun(answers)}
      onEdit={() => router.push(EDIT_HREF)}
      onRerun={rerun}
    />
  );
}

/** `?search=<id>`: a stored search (after a run, Back from a recipe, or a reload). */
function StoredResults({ searchId }: { searchId: string }) {
  const router = useRouter();
  const online = useOnline();
  const rerun = useRerun();
  const current = liveRun();
  const fresh = current && String(current.state.searchId) === searchId && current.state.status !== "running" ? current : null;
  const search = useApi<CookSearch>(fresh ? null : `/api/v1/cook/searches/${searchId}`);
  if (fresh) {
    const answers = loadPending(fresh.run);
    return <ResultsView data={fromState(fresh.state)} answers={answers} error={null} online={online} onRetry={() => answers && rerun(answers)} onEdit={() => router.push(EDIT_HREF)} onRerun={rerun} />;
  }
  if (search.loading && !search.data) return <Skeleton cards={3} label="Loading your results" />;
  if (!search.data) return <ErrorState error={search.error} onRetry={() => void search.reload()} />;
  const answers = search.data.answers as CookAnswers;
  return <ResultsView data={fromSearch(search.data)} answers={answers} error={null} online={online} onRetry={() => rerun(answers)} onEdit={() => router.push(EDIT_HREF)} onRerun={rerun} />;
}

function Results() {
  const params = useSearchParams();
  const run = params.get("run");
  const search = params.get("search");
  if (search) return <StoredResults searchId={search} />;
  if (run) return <LiveResults run={run} />;
  return <EmptyState message="Nothing to search for yet." action={{ label: "A meal now", href: EDIT_HREF }} />;
}

// C5 Results for a meal now (FLOW_SPEC §7): /cook/results/?run=<key> while it streams, ?search=<id> after.
export default function ResultsPage() {
  return (
    <Page>
      <Results />
    </Page>
  );
}
