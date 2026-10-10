"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { ApiError, describeError } from "@/lib/api/client";

import { Pottle } from "./Pottle";
import styles from "./States.module.css";

/** Loading: skeleton cards in the final layout, never a bare spinner (FLOW_SPEC §5.5). */
export function Skeleton({ cards = 2, label = "Loading" }: { cards?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} aria-busy="true">
      {Array.from({ length: cards }, (_, i) => (
        <div key={i} className={`card ${styles.skeleton}`}>
          <span className={styles.bar} style={{ width: "55%" }} />
          <span className={styles.bar} style={{ width: "85%" }} />
          <span className={styles.bar} style={{ width: "40%" }} />
        </div>
      ))}
    </div>
  );
}

type Action = { label: string; href?: string; onClick?: () => void; disabled?: boolean };

function ActionButton({ action, primary }: { action: Action; primary?: boolean }) {
  const className = primary ? "btn btn-primary btn-block" : "btn btn-block";
  if (action.href) {
    return (
      <Link href={action.href} className={className}>
        {action.label}
      </Link>
    );
  }
  return (
    <button type="button" className={className} onClick={action.onClick} disabled={action.disabled}>
      {action.label}
    </button>
  );
}

/** Empty: Pottle (idle), one sentence, one action. */
export function EmptyState({ message, action, secondary }: { message: string; action?: Action; secondary?: Action }) {
  return (
    <section className={`card ${styles.center}`}>
      <Pottle state="idle" size={72} />
      <p className={styles.message}>{message}</p>
      {action && <ActionButton action={action} primary />}
      {secondary && (
        <div className={styles.secondary}>
          <ActionButton action={secondary} />
        </div>
      )}
    </section>
  );
}

/** Error: Pottle (oops), the problem's title in plain words, one sentence of detail, Try again, and a
 * Details expander with the server's problem text and run id. */
export function ErrorState({ error, title, onRetry, runId }: { error: unknown; title?: string; onRetry?: () => void; runId?: number | null }) {
  const api = error instanceof ApiError ? error : null;
  const offline = error instanceof TypeError;
  const heading = title ?? (offline ? "Can't reach Mealbro" : (api?.title ?? "That didn't work"));
  const sentence = offline
    ? "You're offline or the server can't be reached. Try again in a moment."
    : api?.detail || "Try again in a moment.";
  return (
    <section className={`card ${styles.center}`} role="alert">
      <Pottle state="oops" size={72} />
      <h2 className={styles.title}>{heading}</h2>
      <p className={styles.message}>{sentence}</p>
      {onRetry && <ActionButton action={{ label: "Try again", onClick: onRetry }} primary />}
      {(api || runId) && (
        <details className={styles.details}>
          <summary>Details</summary>
          <p className="small">{describeError(error)}</p>
          {api && api.diagnostics.length > 0 && (
            <ul className="small">
              {api.diagnostics.map((d, i) => (
                <li key={`${i}-${d.message}`}>{d.message}</li>
              ))}
            </ul>
          )}
          {runId ? <p className="small muted">Run {runId}</p> : null}
        </details>
      )}
    </section>
  );
}

/** Under a control that needs the server while you're offline. */
export function NeedsConnection({ children = "Needs a connection" }: { children?: ReactNode }) {
  return <p className={styles.needs}>{children}</p>;
}
