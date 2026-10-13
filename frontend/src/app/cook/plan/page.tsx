"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useOnline } from "@/components/AppShell";
import { Page } from "@/components/Page";
import { NoPlanFits } from "@/components/plan/NoPlanFits";
import { PlanView, type SwapProps } from "@/components/plan/PlanView";
import { SwapToast } from "@/components/plan/Swap";
import { SyncNote } from "@/components/Status";
import { BuildingSteps } from "@/components/ui/BuildingSteps";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { api, ApiError } from "@/lib/api/client";
import type { CookAnswers, GenerationRun, Meal, PlanListItem, PlanStreamEvent, PlanSummary, SettingsOut, SwapResult } from "@/lib/api/types";
import { loadPending, savePending } from "@/lib/cook/answers";
import { prepDraftFromAnswers, prepFixes, savePrepDraft } from "@/lib/cook/prep";
import { prepStages, startPrepRun, usePrepRun } from "@/lib/cook/prepRun";
import { useApi } from "@/lib/hooks/useApi";
import { mealKey, type SwappedAway, undoSwap, withSwappedAway } from "@/lib/plan/swap";

const PREP_START = "/cook/ask/?mode=prep&step=amount&fresh=1";
const EDIT = "/cook/ask/?mode=prep&step=amount";

/** Send changed answers again (a "no plan fits" fix); the draft follows, so Edit shows them. */
function useRerun() {
  const router = useRouter();
  return (answers: CookAnswers) => {
    savePrepDraft(prepDraftFromAnswers(answers));
    router.push(`/cook/plan/?run=${savePending(answers)}`);
  };
}

/** C4 Building for meal prep (`?run=<key>`): the real stages as they stream, then the plan (or why none fits). */
function Building({ run }: { run: string }) {
  const router = useRouter();
  const [answers] = useState<CookAnswers | null>(() => loadPending(run));
  const live = usePrepRun(run);
  const settings = useApi<SettingsOut>("/api/v1/settings");
  const rerun = useRerun();
  const [recovering, setRecovering] = useState(false);

  useEffect(() => {
    if (answers) startPrepRun(run, answers);
  }, [run, answers]);

  const state = live?.state;
  useEffect(() => {
    if (state?.status === "succeeded" && state.planId !== null) router.replace(`/cook/plan/?id=${state.planId}`);
  }, [state, router]);

  // the connection dropped: the run still finishes on the server, so look for its plan
  useEffect(() => {
    if (state?.status !== "lost" || state.runId === null || recovering) return;
    setRecovering(true);
    api<GenerationRun>(`/api/v1/generation-runs/${state.runId}`)
      .then((r) => {
        if (r.status === "succeeded" && r.plan_id) router.replace(`/cook/plan/?id=${r.plan_id}`);
      })
      .catch(() => undefined);
  }, [state, router, recovering]);

  if (!answers) return <EmptyState message="Nothing to plan yet." action={{ label: "Meal prep", href: PREP_START }} />;
  if (!live) return <Skeleton cards={2} label="Building your plan" />;
  if (live.error) {
    const refused = live.error instanceof ApiError && live.error.status === 422;
    return (
      <>
        <ErrorState error={live.error} onRetry={refused ? undefined : () => rerun(answers)} />
        {refused && <EmptyState message="Change your answers and try again." action={{ label: "Edit answers", href: EDIT }} />}
      </>
    );
  }
  const s = live.state;
  if (s.status === "infeasible" || (s.status === "failed" && s.problem)) {
    const event = { event: "result", run_id: s.runId ?? 0, elapsed_s: s.elapsedS, status: s.status, problem: s.problem, notes: s.notes } as PlanStreamEvent;
    return (
      <>
        <NoPlanFits event={event} actions={prepFixes(answers, settings.data?.settings ?? null, rerun)} />
        <button type="button" className="btn btn-block" onClick={() => router.push(EDIT)}>
          Edit answers
        </button>
      </>
    );
  }
  if (s.status === "lost" || s.status === "failed") {
    return <ErrorState error={null} title="Lost the connection" onRetry={() => rerun(answers)} runId={s.runId} />;
  }
  return <BuildingSteps stages={prepStages(s)} waitS={s.wait?.seconds ?? null} waitStartedAt={s.wait?.startedAt ?? null} elapsedS={s.elapsedS} onStop={() => router.push("/cook/")} />;
}

type Toast = { message: string; planId: number; undoPlanId: number };

/** Swap (step 2b.6): the swapped-in meal highlighted, the toast with Undo, and the recipes swapped away per
 * meal (never offered again for it). Each swap is a new version of the plan, so the address follows it. */
function useSwaps(setPlan: (plan: PlanSummary) => void) {
  const router = useRouter();
  const [away, setAway] = useState<SwappedAway>({});
  const [highlight, setHighlight] = useState<number | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [undoing, setUndoing] = useState(false);
  const [error, setError] = useState<unknown>(null);

  function onSwapped(result: SwapResult, meal: Meal) {
    setAway((a) => withSwappedAway(a, mealKey(meal.eat_on, meal.slot), meal.recipe_version_id));
    setHighlight(result.plan_meal_id);
    setError(null);
    setToast({ message: result.message, planId: result.plan_id, undoPlanId: result.undo_plan_id });
    setPlan(result.plan);
    router.replace(`/cook/plan/?id=${result.plan_id}`);
  }

  async function undo() {
    if (!toast) return;
    setUndoing(true);
    setError(null);
    try {
      const restored = await undoSwap(toast.planId);
      setToast(null);
      setHighlight(null);
      setPlan(restored);
      router.replace(`/cook/plan/?id=${restored.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setUndoing(false);
    }
  }

  const swap: SwapProps = { away, highlight, onSwapped };
  const banner = toast ? <SwapToast message={toast.message} undoing={undoing} error={error} onUndo={() => void undo()} onDismiss={() => setToast(null)} /> : null;
  return { swap, banner };
}

/** One plan (`?id=`, or `?plan=` from an old day link with `date=`), or your current plan (no id). */
function Plan({ id, scrollTo }: { id: string | null; scrollTo: string | null }) {
  const online = useOnline();
  const list = useApi<PlanListItem[]>(id ? null : "/api/v1/plans?limit=10");
  const current = list.data?.find((p) => p.is_current);
  const planId = id ?? (current ? String(current.id) : null);
  const plan = useApi<PlanSummary>(planId ? `/api/v1/plans/${planId}` : null);
  const { swap, banner } = useSwaps((next) => plan.setData(next));

  useEffect(() => {
    if (plan.data && scrollTo) document.getElementById(`day-${scrollTo}`)?.scrollIntoView?.();
  }, [plan.data, scrollTo]);

  if (list.loading || (plan.loading && !plan.data)) return <Skeleton cards={3} label="Loading your plan" />;
  if (!planId) {
    if (list.error) return <ErrorState error={list.error} onRetry={() => void list.reload()} />;
    return <EmptyState message="No plan yet. Tell me what you're prepping and I'll build one." action={{ label: "Meal prep", href: PREP_START }} />;
  }
  if (!plan.data) return <ErrorState error={plan.error} onRetry={() => void plan.reload()} />;
  return (
    <>
      <SyncNote syncedAt={plan.syncedAt} fromCache={plan.fromCache} />
      {banner}
      <PlanView plan={plan.data} online={online} onAccepted={(out) => plan.setData(out)} swap={swap} />
    </>
  );
}

function PlanScreen() {
  const params = useSearchParams();
  const run = params.get("run");
  if (run) return <Building run={run} />;
  return <Plan id={params.get("id") ?? params.get("plan")} scrollTo={params.get("date")} />;
}

// C6 Results: meal prep, also the current-plan view (FLOW_SPEC §7): /cook/plan/?run=<key> while it builds,
// ?id=<plan id> after; with no id, your current plan.
export default function CookPlanPage() {
  return (
    <Page>
      <PlanScreen />
    </Page>
  );
}
