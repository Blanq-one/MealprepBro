"use client";

import { useSearchParams } from "next/navigation";

import { useOnline } from "@/components/AppShell";
import { CookDayMode } from "@/components/cook/CookDayMode";
import { CookingMode } from "@/components/cook/CookingMode";
import { Page } from "@/components/Page";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import type { BatchDetail, PlanSummary } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";

/** A whole cook day (`?plan=<id>&day=<date>`): its timeline across dishes (2b.7, FLOW_SPEC §20.4). */
function CookDay({ planId, day }: { planId: string; day: string }) {
  const plan = useApi<PlanSummary>(`/api/v1/plans/${planId}`);
  const online = useOnline();
  if (plan.loading && !plan.data) return <Skeleton cards={2} label="Loading your cook day" />;
  if (!plan.data) return <ErrorState error={plan.error} onRetry={() => void plan.reload()} />;
  const found = plan.data.days.find((d) => d.day === day);
  if (!found || !plan.data.batches.some((b) => b.cook_on === day)) {
    return <EmptyState message="Nothing to cook that day." action={{ label: "Back to your plan", href: `/cook/plan/?id=${planId}` }} />;
  }
  return <CookDayMode plan={plan.data} day={found} online={online} />;
}

// Cooking mode: /cook/cooking/?batch=<id>, or a whole cook day: ?plan=<id>&day=<date>. The tab bar is hidden
// here (FLOW_SPEC §3).
function Cooking() {
  const params = useSearchParams();
  const batchId = params.get("batch");
  const planId = params.get("plan");
  const day = params.get("day");
  const batch = useApi<BatchDetail>(batchId ? `/api/v1/cook-batches/${batchId}` : null);
  const online = useOnline();
  if (planId && day) return <CookDay planId={planId} day={day} />;
  if (!batchId) return <EmptyState message="Open a recipe to cook it." action={{ label: "Back to Cook", href: "/cook/" }} />;
  if (batch.loading && !batch.data) return <Skeleton cards={2} label="Loading the recipe" />;
  if (!batch.data) return <ErrorState error={batch.error} onRetry={() => void batch.reload()} />;
  return <CookingMode batch={batch.data} online={online} />;
}

export default function CookingPage() {
  return (
    <Page>
      <Cooking />
    </Page>
  );
}
