"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { useOnline } from "@/components/AppShell";
import { GroceryChecklist, type ItemOverride } from "@/components/GroceryChecklist";
import { Page } from "@/components/Page";
import { ProblemNotice, SyncNote } from "@/components/Status";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api/client";
import type { GroceryComplete, GroceryItem, GroceryItemPatch, GroceryList, PlanListItem } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";
import { appQueue } from "@/lib/offline/queue";

type GroupBy = "store" | "category";

function Grocery() {
  const params = useSearchParams();
  const requested = params.get("plan");
  const plans = useApi<PlanListItem[]>(requested ? null : "/api/v1/plans?limit=10");
  const current = plans.data?.find((p) => p.is_current) ?? plans.data?.[0];
  const planId = requested ?? (current ? String(current.id) : null);
  const [groupBy, setGroupBy] = useState<GroupBy>("store");
  const list = useApi<GroceryList>(planId ? `/api/v1/plans/${planId}/grocery-list?group_by=${groupBy}` : null);
  const [overrides, setOverrides] = useState<Record<number, ItemOverride>>({});
  const [completing, setCompleting] = useState(false);
  const [completed, setCompleted] = useState<GroceryComplete | null>(null);
  const [error, setError] = useState<unknown>(null);
  const online = useOnline();

  function patch(item: GroceryItem, changes: GroceryItemPatch) {
    setOverrides((o) => ({
      ...o,
      [item.id]: {
        ...o[item.id],
        ...(changes.checked !== undefined ? { checked: changes.checked ?? false } : {}),
        ...(changes.purchased_amount ? { purchased: `${changes.purchased_amount} ${changes.purchased_unit ?? ""}`.trim() } : {}),
      },
    }));
    const queue = appQueue();
    queue.enqueue({
      method: "PATCH",
      url: `/api/v1/grocery-items/${item.id}`,
      body: changes as Record<string, unknown>,
      label: `${changes.checked === false ? "Uncheck" : "Check off"} ${item.name}`,
    });
    void queue.replay().then((result) => {
      if (result.sent > 0 && result.kept === 0) void list.reload().then(() => setOverrides({}));
    });
  }

  async function done() {
    if (!list.data) return;
    setCompleting(true);
    setError(null);
    try {
      const pending = await appQueue().replay();
      if (pending.kept > 0) throw new Error("Some check-offs haven't synced yet. Try again when you're online.");
      setCompleted(
        await api<GroceryComplete>(`/api/v1/grocery-lists/${list.data.id}/complete`, { method: "POST", json: {} }),
      );
      await list.reload();
    } catch (e) {
      setError(e);
    } finally {
      setCompleting(false);
    }
  }

  if (plans.loading || (list.loading && !list.data)) return <Skeleton cards={3} label="Loading your grocery list" />;
  if (!planId) {
    if (plans.error) return <ErrorState error={plans.error} onRetry={() => void plans.reload()} />;
    return (
      <>
        <h1>Grocery</h1>
        <EmptyState message="No list yet." action={{ label: "Plan a week", href: "/plan/new/" }} />
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
        <button type="button" className="btn btn-primary btn-block" onClick={done} disabled={completing || !online}>
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
