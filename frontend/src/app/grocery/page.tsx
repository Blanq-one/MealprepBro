"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { useOnline } from "@/components/AppShell";
import { useGroceryChecks } from "@/components/grocery/useGroceryChecks";
import { GroceryChecklist } from "@/components/GroceryChecklist";
import { Page } from "@/components/Page";
import { ProblemNotice, SyncNote } from "@/components/Status";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import type { GroceryList, PlanListItem } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";

type GroupBy = "store" | "category";

function Grocery() {
  const params = useSearchParams();
  const requested = params.get("plan");
  const plans = useApi<PlanListItem[]>(requested ? null : "/api/v1/plans?limit=10");
  const current = plans.data?.find((p) => p.is_current) ?? plans.data?.[0];
  const planId = requested ?? (current ? String(current.id) : null);
  const [groupBy, setGroupBy] = useState<GroupBy>("store");
  const list = useApi<GroceryList>(planId ? `/api/v1/plans/${planId}/grocery-list?group_by=${groupBy}` : null);
  const { overrides, patch, done, completing, completed, error } = useGroceryChecks(list);
  const online = useOnline();

  if (plans.loading || (list.loading && !list.data)) return <Skeleton cards={3} label="Loading your grocery list" />;
  if (!planId) {
    if (plans.error) return <ErrorState error={plans.error} onRetry={() => void plans.reload()} />;
    return (
      <>
        <h1>Grocery</h1>
        <EmptyState message="No list yet." action={{ label: "Meal prep", href: "/cook/ask/?mode=prep&step=amount&fresh=1" }} />
      </>
    );
  }
  if (!list.data) return <ErrorState error={list.error ?? plans.error} onRetry={() => void list.reload()} />;
  const g = list.data;
  const isDone = g.status === "done";

  return (
    <>
      <h1>Grocery</h1>
      <section className="card" aria-label="This trip">
        <p className="small muted" style={{ margin: 0 }}>
          This trip
        </p>
        <p style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0 0 4px" }}>{g.cash_split_display}</p>
        <p className="small muted" style={{ margin: 0 }}>
          {g.checked_count} of {g.to_check_count} checked
        </p>
      </section>
      <SyncNote syncedAt={list.syncedAt} fromCache={list.fromCache} />
      <Segmented
        label="Group by"
        options={[
          { value: "store", label: "By store" },
          { value: "category", label: "By category" },
        ]}
        value={groupBy}
        onChange={setGroupBy}
      />
      {!g.complete && g.unpriced.length > 0 && (
        <p className="notice notice-warn">No price yet for {g.unpriced.join(", ")}.</p>
      )}
      <GroceryChecklist list={g} overrides={overrides} disabled={isDone} onPatch={patch} />
      <ProblemNotice error={error} />
      {completed && (
        <section className="card" role="status">
          <h2>{completed.already_done ? "Already done" : "Done shopping"}</h2>
          <p>
            {completed.lots_created} item{completed.lots_created === 1 ? "" : "s"} added to your inventory,{" "}
            {completed.prices_recorded} price{completed.prices_recorded === 1 ? "" : "s"} recorded.
          </p>
          {completed.not_bought.length > 0 && <p className="muted small">Not bought: {completed.not_bought.join(", ")}</p>}
        </section>
      )}
      {!isDone ? (
        <button type="button" className="btn btn-primary btn-block" onClick={() => void done()} disabled={completing || !online}>
          {completing ? "Saving…" : online ? "Done shopping" : "Done shopping (needs a connection)"}
        </button>
      ) : (
        !completed && <p className="badge badge-accent">This trip is done.</p>
      )}
    </>
  );
}

export default function GroceryPage() {
  return (
    <Page>
      <Grocery />
    </Page>
  );
}
