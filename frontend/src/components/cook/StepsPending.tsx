"use client";

import { clockLabel, useCountdown } from "@/components/ui/BuildingSteps";
import { Pottle } from "@/components/ui/Pottle";
import type { StepsState } from "@/lib/cook/steps";

export const DAILY_STEPS = "That's today's recipe-writing allowance; back tomorrow. Saved recipes still open.";

/** The Steps section of a new idea until its steps are written (C8, E19): its one-line method, then
 * "Writing the steps for this one…" with Pottle working, the countdown during a rate-limit wait, or what
 * happened and one tap to continue. Never the error pattern for a rate limit. */
export function StepsPending({
  method,
  state,
  online,
  onRetry,
}: {
  method: string;
  state: StepsState | null;
  online: boolean;
  onRetry: () => void;
}) {
  const wait = useCountdown(state?.wait?.seconds ?? null, state?.wait?.startedAt ?? null);
  const retry = useCountdown(state?.retry?.seconds ?? null, state?.retry?.startedAt ?? null);
  const cooling = retry !== null && retry > 0;
  return (
    <section className="card" aria-labelledby="steps-h" aria-busy={state?.status === "writing" ? true : undefined}>
      <h2 id="steps-h">Steps</h2>
      {method && <p className="muted">{method}</p>}
      {!online ? (
        <p>The steps need a connection.</p>
      ) : state?.status === "daily" ? (
        <p>{DAILY_STEPS}</p>
      ) : state?.status === "failed" ? (
        <>
          <p role="alert">I couldn&apos;t write the steps just now.</p>
          <button type="button" className="btn" onClick={onRetry}>
            Try again
          </button>
        </>
      ) : state?.status === "waiting" ? (
        <>
          <p role="status">The recipe service needs a short breather.</p>
          <button type="button" className="btn" disabled={cooling} onClick={onRetry}>
            {cooling ? `Ready in ${clockLabel(retry)}` : "Write the steps"}
          </button>
        </>
      ) : (
        <div className="row" role="status">
          <Pottle state="working" size={40} decorative />
          <p>{wait !== null && wait > 0 ? `The recipe service needs a short breather. Back in ${clockLabel(wait)}` : "Writing the steps for this one…"}</p>
        </div>
      )}
    </section>
  );
}
