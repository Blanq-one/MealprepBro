"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { DayList } from "@/components/DayList";
import { Page } from "@/components/Page";
import { ProblemNotice, Spinner, SyncNote } from "@/components/Status";
import { PlanNotices, WeekSummary } from "@/components/WeekSummary";
import { api } from "@/lib/api/client";
import type { PlanListItem, PlanSummary } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";

function Week() {
  const params = useSearchParams();
  const requested = params.get("id");
  const list = useApi<PlanListItem[]>(requested ? null : "/api/v1/plans?limit=10");
  const current = list.data?.find((p) => p.is_current) ?? list.data?.[0];
  const id = requested ?? (current ? String(current.id) : null);
  const plan = useApi<PlanSummary>(id ? `/api/v1/plans/${id}` : null);
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<unknown>(null);

  if (list.loading || plan.loading) return <Spinner />;
  if (list.error || plan.error) {
    return (
      <>
        <ProblemNotice error={list.error ?? plan.error} />
        <SyncNote syncedAt={plan.syncedAt ?? list.syncedAt} fromCache={false} />
      </>
    );
  }
  if (!plan.data) {
    return (
      <section className="card">
        <h1>No plan yet</h1>
        <p className="muted">Plan a week from your saved recipes, inventory and prices.</p>
        <Link href="/plan/new/" className="btn btn-primary btn-block">
          Plan a week
        </Link>
      </section>
    );
  }

  const summary = plan.data;
  async function accept() {
    setAccepting(true);
    setAcceptError(null);
    try {
      plan.setData(await api<PlanSummary>(`/api/v1/plans/${summary.id}/accept`, { method: "POST" }));
    } catch (error) {
      setAcceptError(error);
    } finally {
      setAccepting(false);
    }
  }

  return (
    <>
      <WeekSummary plan={summary} />
      <SyncNote syncedAt={plan.syncedAt} fromCache={plan.fromCache} />
      <ProblemNotice error={acceptError} />
      <div className="row" style={{ flexWrap: "wrap", marginBottom: 12 }}>
        {summary.status === "draft" && (
          <button type="button" className="btn btn-primary" onClick={accept} disabled={accepting}>
            {accepting ? "Accepting…" : "Accept plan"}
          </button>
        )}
        <Link href={`/grocery/?plan=${summary.id}`} className="btn">
          Grocery list
        </Link>
        <Link href="/plan/new/" className="btn">
          Plan another week
        </Link>
      </div>
      <PlanNotices plan={summary} />
      <DayList plan={summary} />
    </>
  );
}

export default function WeekPage() {
  return (
    <Page>
      <Week />
    </Page>
  );
}
