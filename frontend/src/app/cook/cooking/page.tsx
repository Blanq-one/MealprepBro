"use client";

import { useSearchParams } from "next/navigation";

import { useOnline } from "@/components/AppShell";
import { CookingMode } from "@/components/cook/CookingMode";
import { Page } from "@/components/Page";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import type { BatchDetail } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";

// Cooking mode: /cook/cooking/?batch=<id>. The tab bar is hidden here (FLOW_SPEC §3).
function Cooking() {
  const params = useSearchParams();
  const batchId = params.get("batch");
  const batch = useApi<BatchDetail>(batchId ? `/api/v1/cook-batches/${batchId}` : null);
  const online = useOnline();
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
