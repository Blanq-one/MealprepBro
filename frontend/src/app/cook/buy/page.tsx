"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useOnline } from "@/components/AppShell";
import { useGroceryChecks } from "@/components/grocery/useGroceryChecks";
import { GroceryChecklist } from "@/components/GroceryChecklist";
import { Page } from "@/components/Page";
import { ProblemNotice } from "@/components/Status";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import type { GroceryList } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";

/** Buy first (C8, Cook this): the one-meal plan's list, checked off with the grocery endpoints. Done
 * shopping adds what you bought to your pantry, then cooking mode opens. */
function BuyFirst({ batchId, planId }: { batchId: string; planId: string }) {
  const router = useRouter();
  const online = useOnline();
  const list = useApi<GroceryList>(`/api/v1/plans/${planId}/grocery-list?group_by=store`);
  const { overrides, patch, done, completing, error } = useGroceryChecks(list);
  const cooking = `/cook/cooking/?batch=${batchId}`;

  if (list.loading && !list.data) return <Skeleton cards={2} label="Loading what to buy" />;
  if (!list.data) return <ErrorState error={list.error} onRetry={() => void list.reload()} />;
  const g = list.data;
  return (
    <>
      <h1>Buy first</h1>
      <p className="muted">Check these off as you get them. {g.cash_split_display}</p>
      {!g.complete && g.unpriced.length > 0 && <p className="notice notice-warn">No price yet for {g.unpriced.join(", ")}.</p>}
      <GroceryChecklist list={g} overrides={overrides} disabled={g.status === "done"} onPatch={patch} />
      <ProblemNotice error={error} />
      {g.status !== "done" ? (
        <button
          type="button"
          className="btn btn-primary btn-block"
          disabled={completing || !online}
          onClick={() =>
            void done().then((out) => {
              if (out) router.push(cooking);
            })
          }
        >
          {completing ? "Saving…" : online ? "Done shopping, start cooking" : "Done shopping (needs a connection)"}
        </button>
      ) : (
        <Link href={cooking} className="btn btn-primary btn-block">
          Start cooking
        </Link>
      )}
      <Link href={cooking} className="btn btn-link btn-block">
        I have everything, start cooking
      </Link>
    </>
  );
}

function Buy() {
  const params = useSearchParams();
  const batch = params.get("batch");
  const plan = params.get("plan");
  if (!batch || !plan) return <EmptyState message="Nothing to buy here." action={{ label: "Back to Cook", href: "/cook/" }} />;
  return <BuyFirst batchId={batch} planId={plan} />;
}

export default function BuyPage() {
  return (
    <Page>
      <Buy />
    </Page>
  );
}
