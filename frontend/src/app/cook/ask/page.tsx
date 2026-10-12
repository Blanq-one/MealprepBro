"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useOnline } from "@/components/AppShell";
import { GoalsStep } from "@/components/cook/GoalsStep";
import { HaveStep } from "@/components/cook/HaveStep";
import { AmountStep, CookStyleStep, PrepGoalsStep, ShopStep } from "@/components/cook/PrepSteps";
import { Page } from "@/components/Page";
import { Skeleton } from "@/components/ui/States";
import type { CookHome, SettingsOut } from "@/lib/api/types";
import { buildAnswers, clearDraft, draftFromAnswers, emptyDraft, loadDraft, type MealNowDraft, saveDraft, savePending } from "@/lib/cook/answers";
import {
  buildPrepAnswers,
  clearPrepDraft,
  emptyPrepDraft,
  loadPrepDraft,
  PREP_STEPS,
  type PrepDraft,
  prepDraftFromAnswers,
  type PrepStep,
  savePrepDraft,
} from "@/lib/cook/prep";
import { useApi } from "@/lib/hooks/useApi";

const ASK = "/cook/ask/?mode=now";

// The meal-now questions (FLOW_SPEC §7 C2–C3): /cook/ask/?mode=now&step=goals, then step=have. A fresh start
// from Cook home pre-fills from your last meal-now answers; Back and Edit keep the draft.
function MealNowQuestions() {
  const params = useSearchParams();
  const router = useRouter();
  const step = params.get("step") === "have" ? "have" : "goals";
  const fresh = params.get("fresh") === "1";
  const home = useApi<CookHome>("/api/v1/cook/home");
  const settings = useApi<SettingsOut>("/api/v1/settings");
  const online = useOnline();
  const [draft, setDraft] = useState<MealNowDraft | null>(() => (fresh ? null : (loadDraft() ?? null)));
  const last = home.data?.last.find((l) => l.mode === "now") ?? null;

  useEffect(() => {
    // a fresh start (or a draft lost with the tab) starts from your last answers once they arrive
    if (draft !== null || home.loading) return;
    clearDraft();
    setDraft(last ? draftFromAnswers(last.answers) : emptyDraft());
    if (fresh) router.replace(`${ASK}&step=goals`);
  }, [draft, home.loading, last, fresh, router]);

  useEffect(() => {
    if (draft) saveDraft(draft);
  }, [draft]);

  if (!draft) return <Skeleton cards={2} label="Getting your last answers" />;
  const householdSize = settings.data?.settings.household_size ?? null;

  if (step === "goals") {
    return <GoalsStep draft={draft} householdSize={householdSize} onChange={setDraft} onBack={() => router.push("/cook/")} onNext={() => router.push(`${ASK}&step=have`)} />;
  }
  return (
    <HaveStep
      draft={draft}
      onChange={setDraft}
      online={online}
      last={last}
      onBack={() => router.push(`${ASK}&step=goals`)}
      onFind={() => {
        const run = savePending(buildAnswers(draft));
        router.push(`/cook/results/?run=${run}`);
      }}
    />
  );
}

const PREP = "/cook/ask/?mode=prep";

// The meal-prep questions (FLOW_SPEC §7 C1, C1b, C2, C3, C3b): /cook/ask/?mode=prep&step=amount, when, goals,
// have, shop. A fresh start from Cook home pre-fills from your last meal-prep answers; Back keeps the draft.
function MealPrepQuestions() {
  const params = useSearchParams();
  const router = useRouter();
  const raw = params.get("step");
  const step: PrepStep = (PREP_STEPS as readonly string[]).includes(raw ?? "") ? (raw as PrepStep) : "amount";
  const fresh = params.get("fresh") === "1";
  const home = useApi<CookHome>("/api/v1/cook/home");
  const loaded = useApi<SettingsOut>("/api/v1/settings");
  const online = useOnline();
  const [draft, setDraft] = useState<PrepDraft | null>(() => (fresh ? null : (loadPrepDraft() ?? null)));
  const last = home.data?.last.find((l) => l.mode === "prep") ?? null;
  const settings = loaded.data?.settings ?? null;

  useEffect(() => {
    if (draft !== null || home.loading) return;
    clearPrepDraft();
    setDraft(last ? prepDraftFromAnswers(last.answers) : emptyPrepDraft());
    if (fresh) router.replace(`${PREP}&step=amount`);
  }, [draft, home.loading, last, fresh, router]);

  useEffect(() => {
    if (draft) savePrepDraft(draft);
  }, [draft]);

  if (!draft) return <Skeleton cards={2} label="Getting your last answers" />;
  const at = PREP_STEPS.indexOf(step);
  const go = (to: PrepStep | null) => router.push(to === null ? "/cook/" : `${PREP}&step=${to}`);
  const props = {
    draft,
    settings,
    onChange: setDraft,
    onBack: () => go(at > 0 ? (PREP_STEPS[at - 1] as PrepStep) : null),
    onNext: () => go(PREP_STEPS[at + 1] as PrepStep),
  };
  switch (step) {
    case "amount":
      return <AmountStep {...props} />;
    case "when":
      return <CookStyleStep {...props} />;
    case "goals":
      return <PrepGoalsStep {...props} />;
    case "have":
      return <HaveStep draft={draft} onChange={setDraft} online={online} last={last} onBack={props.onBack} onFind={props.onNext} primaryLabel="Next" progress={{ step: 4, total: PREP_STEPS.length }} sends={false} />;
    default:
      return (
        <ShopStep
          {...props}
          online={online}
          onNext={() => {
            const run = savePending(buildPrepAnswers(draft, settings));
            router.push(`/cook/plan/?run=${run}`);
          }}
        />
      );
  }
}

function Questions() {
  const params = useSearchParams();
  if (params.get("mode") === "prep") return <MealPrepQuestions />;
  return <MealNowQuestions />;
}

export default function AskPage() {
  return (
    <Page>
      <Questions />
    </Page>
  );
}
