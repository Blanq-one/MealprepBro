"use client";

// Swap (FLOW_SPEC C6, step 2b.6, AA4). ⇄ Swap on a meal row opens a sheet with 3-5 other meals that fit the same
// slot, day, fridge or freezer and time rules, each with what it adds to the groceries and its protein; one tap
// replaces just that meal. Write a new one makes one ideas call (a rate-limit wait is a countdown, never an
// error). The toast after a swap says what else changed, with Undo. Every number and line is the server's.
import { useEffect, useRef, useState } from "react";

import { clockLabel, useCountdown } from "@/components/ui/BuildingSteps";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Emoji } from "@/components/ui/Emoji";
import { Pottle } from "@/components/ui/Pottle";
import { NeedsConnection } from "@/components/ui/States";
import { describeError } from "@/lib/api/client";
import type { Meal, SwapOption, SwapOptionsBody, SwapResult } from "@/lib/api/types";
import { dishIcon } from "@/lib/format/icons";
import { slotLabel } from "@/lib/format/labels";
import { applySwap, initialSwap, reduceSwap, streamSwapOptions, type SwapSheetState } from "@/lib/plan/swap";

import styles from "./Swap.module.css";

function OptionCard({ option, busy, disabled, onPick }: { option: SwapOption; busy: boolean; disabled: boolean; onPick: () => void }) {
  const icon = dishIcon(option.dish_category);
  return (
    <li>
      <button type="button" className={styles.option} disabled={disabled} onClick={onPick} aria-label={`Swap to ${option.title}`}>
        <Emoji symbol={icon.emoji} label={icon.label} className={styles.icon} />
        <span className={styles.text}>
          <span className={styles.title}>
            {option.title}
            {option.is_new && <span className="badge"> New</span>}
            {option.is_draft && <span className="badge badge-warn"> Draft</span>}
          </span>
          <span className={styles.numbers}>{option.numbers.join(" · ")}</span>
          <span className={styles.cost}>{option.cost_delta_display}</span>
          <span className={styles.source}>{option.source_display}</span>
          {option.also_changed.length > 0 && <span className={styles.also}>Also changes: {option.also_changed.join("; ")}</span>}
          {(option.buys ?? []).length > 0 && <span className={styles.also}>Buys: {(option.buys ?? []).join(", ")}</span>}
          {option.steps_ready === false && <span className={styles.also}>Its steps are written when you first open it.</span>}
          {busy && <span className={styles.busy}>Swapping…</span>}
        </span>
      </button>
    </li>
  );
}

/** The sheet for one meal. `away`: the recipes already swapped away for it (never offered again). */
export function SwapSheet({ planId, meal, away, online, onClose, onSwapped }: { planId: number; meal: Meal; away: number[]; online: boolean; onClose: () => void; onSwapped: (result: SwapResult) => void }) {
  const mealId = meal.plan_meal_id ?? 0;
  const [body, setBody] = useState<SwapOptionsBody>({ exclude_version_ids: away, allow_llm: false, allow_buying: false });
  const [state, setState] = useState<SwapSheetState>(initialSwap);
  const [applying, setApplying] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const retried = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setState(initialSwap());
    setError(null);
    retried.current = false;
    streamSwapOptions(planId, mealId, body, (event) => setState((s) => reduceSwap(s, event)), controller.signal)
      .then(() => setState((s) => (s.status === "finding" ? { ...s, status: "lost" } : s)))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e);
        setState((s) => ({ ...s, status: "failed" }));
      });
    return () => controller.abort();
  }, [planId, mealId, body]);

  const waitLeft = useCountdown(state.wait?.seconds ?? null, state.wait?.startedAt ?? null);
  const retryLeft = useCountdown(state.retry?.seconds ?? null, state.retry?.startedAt ?? null);
  useEffect(() => {
    // the call had to wait longer than one request: try again when the countdown ends
    if (state.status === "waiting" && retryLeft === 0 && !retried.current) {
      retried.current = true;
      setBody((b) => ({ ...b }));
    }
  }, [state.status, retryLeft]);

  async function pick(option: SwapOption) {
    setApplying(option.version_id);
    setError(null);
    try {
      const result = await applySwap(planId, mealId, {
        version_id: option.version_id,
        allow_buying: body.allow_buying ?? false,
        offered_version_ids: state.options.map((o) => o.version_id),
        exclude_version_ids: away,
      });
      onSwapped(result);
    } catch (e) {
      setError(e);
    } finally {
      setApplying(null);
    }
  }

  const label = state.current?.label ?? slotLabel(meal.slot);
  const current = state.current;
  const busy = applying !== null;
  return (
    <BottomSheet title={`Swap ${label}`} open onClose={onClose}>
      {current && (
        <p className={styles.now}>
          Now: <strong>{current.title}</strong> · {current.kcal} kcal · {current.protein_g} g protein
        </p>
      )}
      {state.status === "finding" && (
        <div className={styles.working} role="status">
          <Pottle state="working" size={48} decorative />
          <p>{waitLeft !== null && waitLeft > 0 ? `The recipe service needs a short breather. Writing a new one in ${clockLabel(waitLeft)}…` : `${state.message ?? (state.writing ? "Writing a new one" : `Finding another ${slotLabel(meal.slot).toLowerCase()}`)}…`}</p>
        </div>
      )}
      {state.status === "waiting" && (
        <p className="notice" role="status">
          The recipe service needs a short breather. Trying again in {clockLabel(retryLeft ?? 0)}…
        </p>
      )}
      {state.afterShopping && (state.status === "ready" || state.status === "none_fit") && (
        <div className={styles.shopped}>
          <p className="small">{body.allow_buying ? "These may buy what they need; it's added to your list." : "You've done the shopping, so these use what you have."}</p>
          {!body.allow_buying && (
            <button type="button" className="btn btn-link" disabled={!online || busy} onClick={() => setBody({ ...body, allow_llm: false, allow_buying: true })}>
              Allow buying
            </button>
          )}
        </div>
      )}
      {state.status === "ready" && (
        <ul className={styles.options} aria-label="Other meals that fit">
          {state.options.map((option) => (
            <OptionCard key={option.version_id} option={option} busy={applying === option.version_id} disabled={busy || !online} onPick={() => void pick(option)} />
          ))}
        </ul>
      )}
      {state.status === "none_fit" && (
        <div className={styles.none}>
          <Pottle state="oops" size={48} decorative />
          <p>{state.noFit}</p>
        </div>
      )}
      {(state.status === "failed" || state.status === "lost") && (
        <p className="notice notice-danger" role="alert">
          {state.problem ? state.problem.detail : error !== null ? describeError(error) : "Lost the connection. Try again."}
        </p>
      )}
      {state.status !== "failed" && error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
      {state.notes.map((note) => (
        <p key={note} className="small muted">
          {note}
        </p>
      ))}
      {!online && <NeedsConnection />}
      {(state.status === "ready" || state.status === "none_fit") && state.canWriteNew && (
        <button type="button" className="btn btn-block" disabled={!online || busy} onClick={() => setBody({ ...body, allow_llm: true })}>
          Write a new one
        </button>
      )}
      {state.status === "lost" && (
        <button type="button" className="btn btn-block" onClick={() => setBody({ ...body })}>
          Try again
        </button>
      )}
      <button type="button" className="btn btn-block" onClick={onClose} disabled={busy}>
        Keep this one
      </button>
    </BottomSheet>
  );
}

/** ⇄ Swap on a meal row (44 px), with its sheet; `open` is the row's, so the ⋯ sheet can open it too. */
export function SwapButton({ planId, meal, away, online, open, onOpenChange, onSwapped }: { planId: number; meal: Meal; away: number[]; online: boolean; open: boolean; onOpenChange: (open: boolean) => void; onSwapped: (result: SwapResult, meal: Meal) => void }) {
  return (
    <>
      <button type="button" className={styles.swap} disabled={!online} onClick={() => onOpenChange(true)} aria-label={`Swap ${meal.title}`}>
        ⇄ <span className={styles.swapWord}>Swap</span>
      </button>
      {open && (
        <SwapSheet
          planId={planId}
          meal={meal}
          away={away}
          online={online}
          onClose={() => onOpenChange(false)}
          onSwapped={(result) => {
            onOpenChange(false);
            onSwapped(result, meal);
          }}
        />
      )}
    </>
  );
}

/** After a swap: "Swapped. Also changed: … Undo" (C6). */
export function SwapToast({ message, undoing, error, onUndo, onDismiss }: { message: string; undoing: boolean; error: unknown; onUndo: () => void; onDismiss: () => void }) {
  return (
    <div className={styles.toast} role="status">
      <p>{message}</p>
      {error !== null && error !== undefined && <p className={styles.toastError}>{describeError(error)}</p>}
      <span className={styles.toastActions}>
        <button type="button" className="btn btn-link" disabled={undoing} onClick={onUndo}>
          {undoing ? "Undoing…" : "Undo"}
        </button>
        <button type="button" className="btn btn-link" onClick={onDismiss} aria-label="Dismiss">
          ✕
        </button>
      </span>
    </div>
  );
}
