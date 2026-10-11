"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { PlanFailure, PlanProgress } from "@/components/PlanProgress";
import { ProblemNotice } from "@/components/Status";
import { Segmented } from "@/components/ui/Segmented";
import { api } from "@/lib/api/client";
import { streamPlan } from "@/lib/api/ndjson";
import type { GenerationRun, NutritionPriority, PlanRequestBody, PlanStreamEvent } from "@/lib/api/types";
import { nextMonday } from "@/lib/format/dates";
import { centsToInput, parseDollarsToCents } from "@/lib/format/money";

const PRIORITIES: { value: "" | NutritionPriority; label: string }[] = [
  { value: "", label: "My usual (settings)" },
  { value: "protein", label: "High protein" },
  { value: "carb", label: "Carb rich" },
  { value: "iron", label: "Iron rich" },
  { value: "balanced", label: "Balanced" },
];

type Mode = "shop" | "inventory";

export default function NewPlanPage() {
  const router = useRouter();
  const [weekStart, setWeekStart] = useState(nextMonday);
  const [mode, setMode] = useState<Mode>("shop");
  const [money, setMoney] = useState("");
  const [priority, setPriority] = useState<"" | NutritionPriority>("");
  const [allowLlm, setAllowLlm] = useState(true);
  const [running, setRunning] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  const [latest, setLatest] = useState<PlanStreamEvent | null>(null);
  const [failure, setFailure] = useState<PlanStreamEvent | null>(null);
  const [error, setError] = useState<unknown>(null);
  const cents = parseDollarsToCents(money);

  async function recover(runId: number): Promise<boolean> {
    try {
      const run = await api<GenerationRun>(`/api/v1/generation-runs/${runId}`);
      if (run.status === "succeeded" && run.plan_id) {
        router.push(`/plan/?id=${run.plan_id}`);
        return true;
      }
    } catch {
      // still offline: fall through to the error
    }
    return false;
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void plan(mode, cents);
  }

  /** A "no plan fits" fix (2b.4 approval, B): the same week again with the suggested money or mode. */
  function retry(nextMode: Mode, nextCents: number | null) {
    setMode(nextMode);
    setMoney(nextCents === null ? "" : centsToInput(nextCents));
    void plan(nextMode, nextCents);
  }

  async function plan(planMode: Mode, planCents: number | null | undefined) {
    if (running || planCents === undefined) return;
    const request: PlanRequestBody = {
      week_start: weekStart,
      mode: planMode,
      allow_llm: allowLlm,
      ...(priority ? { nutrition_priority: priority } : {}),
      ...(planCents !== null ? (planMode === "shop" ? { budget_cents: planCents } : { topup_cents: planCents }) : {}),
    };
    setRunning(true);
    setStartedAt(Date.now());
    setLatest(null);
    setFailure(null);
    setError(null);
    let runId: number | null = null;
    let result: PlanStreamEvent | null = null;
    try {
      await streamPlan(request, (e) => {
        runId = e.run_id;
        if (e.event === "result") result = e;
        else if (e.event === "progress" || e.event === "started") setLatest(e);
      });
    } catch (e) {
      if (runId !== null && (await recover(runId))) return;
      setError(e);
    }
    const final = result as PlanStreamEvent | null;
    if (final?.status === "succeeded" && final.plan_id) {
      router.push(`/plan/?id=${final.plan_id}`);
      return;
    }
    if (final) setFailure(final);
    else if (runId !== null && !(await recover(runId))) {
      setError(new Error("The connection dropped before the plan finished. Check the week view in a minute."));
    }
    setRunning(false);
  }

  return (
    <form onSubmit={submit}>
      <h1>Plan a week</h1>
      <label htmlFor="week">Week starting</label>
      <input id="week" type="date" value={weekStart} onChange={(e) => setWeekStart(e.target.value)} required />

      <label id="mode-label">What are you doing?</label>
      <Segmented
        label="What are you doing?"
        options={[
          { value: "shop", label: "Shopping" },
          { value: "inventory", label: "Cook from what I have" },
        ]}
        value={mode}
        onChange={setMode}
      />

      <label htmlFor="money">{mode === "shop" ? "Budget for this trip (optional)" : "Top-up allowance (optional)"}</label>
      <input
        id="money"
        inputMode="decimal"
        placeholder={mode === "shop" ? "No limit" : "Buy nothing"}
        value={money}
        onChange={(e) => setMoney(e.target.value)}
        aria-invalid={cents === undefined}
      />
      {cents === undefined && <p className="notice notice-warn">Enter dollars, like 45 or 45.50.</p>}
      <p className="muted small">
        {mode === "shop"
          ? "Uses your inventory first, then builds the grocery list. Stock-up items are listed separately."
          : "Buys nothing unless you allow a top-up; says exactly what's missing if nothing fits."}
      </p>

      <label htmlFor="priority">Nutrition focus</label>
      <select id="priority" value={priority} onChange={(e) => setPriority(e.target.value as "" | NutritionPriority)}>
        {PRIORITIES.map((p) => (
          <option key={p.value} value={p.value}>
            {p.label}
          </option>
        ))}
      </select>

      <label className="row" style={{ fontWeight: 400 }}>
        <input
          type="checkbox"
          checked={allowLlm}
          onChange={(e) => setAllowLlm(e.target.checked)}
          style={{ width: 28, minHeight: 28 }}
        />
        Write new recipes where my saved ones don&apos;t cover a meal
      </label>

      <div style={{ marginTop: 16 }}>
        {running ? (
          <PlanProgress startedAt={startedAt} event={latest} />
        ) : (
          <button type="submit" className="btn btn-primary btn-block" disabled={cents === undefined}>
            Plan this week
          </button>
        )}
      </div>
      {failure && (
        <PlanFailure
          event={failure}
          busy={running}
          actions={{
            onTopUp: (c) => retry("inventory", c),
            onShop: () => retry("shop", null),
            onBudget: (c) => retry("shop", c),
          }}
        />
      )}
      <ProblemNotice error={error} />
    </form>
  );
}
