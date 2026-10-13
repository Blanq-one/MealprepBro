"use client";

// A recipe line's ⋯ (step 2b.6, AA5, AA8): Swap it, Leave it out, I'm out of this, Never use this; for a line
// with a budget equivalent (2b.6 approval, item 4), Classic or budget: always one side in this recipe. An edit saves
// your own version of the recipe; from a plan meal, Also update this week's plan switches that batch to it. A
// swap that cooks differently offers Rewrite steps for this change (one LLM call, only on tap). Every number
// and line is the server's.
import { useEffect, useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { NeedsConnection } from "@/components/ui/States";
import { describeError } from "@/lib/api/client";
import type { LineOptions, PlanUpdate, RecipeEdit, SwapChoice } from "@/lib/api/types";
import { addToList, editLine, lineOptions, neverUse, rewriteSteps, switchedBatch, applyVersionToPlan } from "@/lib/cook/edits";

import styles from "./IngredientMore.module.css";

/** The plan batch the recipe page was opened from (a plan meal). */
export type BatchContext = { id: number; planId: number; cookOn: string };

export const NEVER_NOTE = "On Foods I don't eat: future plans, searches and ideas leave it out. Allow it again in Settings.";
export const DEFAULT_NOTE = "It's the recipe's default from now on, so your next plans use it.";

function Choice({ choice, disabled, onPick }: { choice: SwapChoice; disabled: boolean; onPick: () => void }) {
  return (
    <li>
      <button type="button" className={styles.choice} disabled={disabled} onClick={onPick} aria-label={`Swap to ${choice.name}`}>
        <span className={styles.name}>
          {choice.name} <span className={styles.amount}>{choice.display}</span>
        </span>
        <span className={styles.numbers}>{choice.numbers.join(" · ")} a portion</span>
        {choice.note && <span className={styles.numbers}>{choice.note}</span>}
        {choice.cooking_note && <span className={styles.cook}>{choice.cooking_note}</span>}
      </button>
    </li>
  );
}

export function IngredientSheet({
  versionId,
  lineId,
  name,
  batch,
  online,
  onClose,
  onOpenVersion,
  onPlanUpdated,
}: {
  versionId: number;
  lineId: number;
  name: string;
  batch?: BatchContext | null;
  online: boolean;
  onClose: () => void;
  onOpenVersion: (versionId: number) => void;
  onPlanUpdated?: (update: PlanUpdate, batchId: number | null) => void;
}) {
  const [options, setOptions] = useState<LineOptions | null>(null);
  const [result, setResult] = useState<RecipeEdit | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [never, setNever] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let live = true;
    lineOptions(versionId, lineId, batch?.id)
      .then((o) => {
        if (!live) return;
        setOptions(o);
        setNever(o.never_used);
      })
      .catch((e: unknown) => live && setError(e));
    return () => {
      live = false;
    };
  }, [versionId, lineId, batch?.id]);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const edit = (body: { action: "swap" | "leave_out" | "use_classic" | "use_budget"; ingredient_id?: number }) =>
    run(async () => setResult(await editLine(versionId, { line_id: lineId, batch_id: batch?.id ?? null, ingredient_id: body.ingredient_id ?? null, action: body.action })));
  const locked = busy || !online;

  return (
    <BottomSheet title={name} open onClose={onClose}>
      {error !== null && (
        <p className="notice notice-danger" role="alert">
          {describeError(error)}
        </p>
      )}
      {!online && <NeedsConnection />}
      {result ? (
        <div className={styles.result}>
          <p className="notice" role="status">
            <strong>{result.note}.</strong> {DEFAULT_NOTE}
          </p>
          {result.cooking_note && (
            <>
              <p className="notice notice-safety">{result.cooking_note} The steps it changes are flagged.</p>
              <button type="button" className="btn btn-block" disabled={locked} onClick={() => void run(async () => onOpenVersion((await rewriteSteps(result.version.version_id)).version_id))}>
                Rewrite steps for this change
              </button>
            </>
          )}
          {batch &&
            (result.can_update_plan ? (
              <button
                type="button"
                className="btn btn-primary btn-block"
                disabled={locked}
                onClick={() =>
                  void run(async () => {
                    const update = await applyVersionToPlan(batch.planId, batch.id, result.version.version_id);
                    onPlanUpdated?.(update, switchedBatch(update.plan, batch.cookOn, result.version.version_id));
                  })
                }
              >
                Also update this week&apos;s plan
              </button>
            ) : (
              result.plan_note && <p className="small muted">{result.plan_note}</p>
            ))}
          <button type="button" className="btn btn-block" onClick={() => onOpenVersion(result.version.version_id)}>
            Open your version
          </button>
        </div>
      ) : !options ? (
        error === null && <p role="status">Finding options for {name}…</p>
      ) : (
        <>
          <p className="small muted">{options.display}</p>
          {options.pair && (
            <section aria-labelledby="pair-h">
              <h3 id="pair-h">Classic or budget</h3>
              <p className="small">
                A budget tier cooks this with whichever is cheaper at your stores: {options.pair.classic} (the classic) or {options.pair.budget_display}. Pick one to always use it in this recipe.
              </p>
              <button type="button" className="btn btn-block" disabled={locked} onClick={() => void edit({ action: "use_classic" })}>
                Always the classic: {options.pair.classic}
              </button>
              <button type="button" className="btn btn-block" disabled={locked} onClick={() => void edit({ action: "use_budget" })}>
                Always the budget one: {options.pair.budget}
              </button>
            </section>
          )}
          <section aria-labelledby="swap-h">
            <h3 id="swap-h">Swap it</h3>
            {options.swaps.length > 0 ? (
              <ul className={styles.choices}>
                {options.swaps.map((c) => (
                  <Choice key={c.ingredient_id} choice={c} disabled={locked} onPick={() => void edit({ action: "swap", ingredient_id: c.ingredient_id })} />
                ))}
              </ul>
            ) : (
              <p className="small muted">Nothing from its group or role fits your rules.</p>
            )}
          </section>
          <section aria-labelledby="leave-h">
            <h3 id="leave-h">Leave it out</h3>
            {options.leave_out.allowed ? (
              <>
                <p className="small">{(options.leave_out.numbers ?? []).join(" · ")} a portion</p>
                {options.leave_out.warning && <p className="notice notice-warn small">{options.leave_out.warning}</p>}
                <button type="button" className="btn btn-block" disabled={locked} onClick={() => void edit({ action: "leave_out" })}>
                  Leave out {name}
                </button>
              </>
            ) : (
              <p className="small muted">{options.leave_out.reason}</p>
            )}
          </section>
          <section aria-labelledby="out-h">
            <h3 id="out-h">I&apos;m out of this</h3>
            <p className="small">{options.in_pantry ? "Your pantry still shows some. " : ""}Swap it above, or put it on your shopping list.</p>
            {options.shopping.can_add ? (
              <button type="button" className="btn btn-block" disabled={locked} onClick={() => void run(async () => setMessage((await addToList(versionId, lineId, batch?.id)).message))}>
                Add to shopping list
              </button>
            ) : (
              <p className="small muted">{options.shopping.reason}</p>
            )}
          </section>
          <section aria-labelledby="never-h">
            <h3 id="never-h">Never use this</h3>
            {never ? (
              <p className={styles.never} role="status">
                <span>{NEVER_NOTE}</span>
                <button type="button" className="btn btn-link" disabled={locked} onClick={() => void run(async () => (await neverUse(options.ingredient_id, false), setNever(false)))}>
                  Undo
                </button>
              </p>
            ) : (
              <button type="button" className="btn btn-block" disabled={locked} onClick={() => void run(async () => (await neverUse(options.ingredient_id, true), setNever(true)))}>
                Never use {name}
              </button>
            )}
          </section>
          {message && (
            <p className="notice" role="status">
              {message}
            </p>
          )}
        </>
      )}
      <button type="button" className="btn btn-block" onClick={onClose} disabled={busy}>
        Close
      </button>
    </BottomSheet>
  );
}

/** The ⋯ beside an ingredient line, with its sheet. */
export function IngredientMore(props: Omit<Parameters<typeof IngredientSheet>[0], "onClose">) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className={styles.more} aria-label={`More for ${props.name}`} onClick={() => setOpen(true)}>
        ⋯
      </button>
      {open && <IngredientSheet {...props} onClose={() => setOpen(false)} />}
    </>
  );
}
