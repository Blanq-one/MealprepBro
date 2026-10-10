"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useOnline } from "@/components/AppShell";
import { GoalsStep } from "@/components/cook/GoalsStep";
import { HaveStep } from "@/components/cook/HaveStep";
import { Page } from "@/components/Page";
import { Redirect } from "@/components/Redirect";
import { Skeleton } from "@/components/ui/States";
import type { CookHome, SettingsOut } from "@/lib/api/types";
import { buildAnswers, clearDraft, draftFromAnswers, emptyDraft, loadDraft, type MealNowDraft, saveDraft, savePending } from "@/lib/cook/answers";
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

function Questions() {
  const params = useSearchParams();
  // meal prep's questions arrive with step 2b.7; until then Meal prep opens the existing plan flow (H3)
  if (params.get("mode") === "prep") return <Redirect to="/plan/new/" label="Plan a week" />;
  return <MealNowQuestions />;
}

export default function AskPage() {
  return (
    <Page>
      <Questions />
    </Page>
  );
}
