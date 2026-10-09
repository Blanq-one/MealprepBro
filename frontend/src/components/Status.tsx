import { ApiError, describeError } from "@/lib/api/client";
import { agoLabel } from "@/lib/format/dates";

import styles from "./Status.module.css";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className={styles.spinnerWrap} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

/** An error from the API (problem+json title, detail and diagnostics) or the network. */
export function ProblemNotice({ error, title }: { error: unknown; title?: string }) {
  if (!error) return null;
  const api = error instanceof ApiError ? error : null;
  return (
    <div className="notice notice-danger" role="alert">
      <strong>{title ?? api?.title ?? "Something went wrong"}</strong>
      <div>{api ? api.detail || null : describeError(error)}</div>
      {api && api.diagnostics.length > 0 && (
        <ul className={styles.diagnostics}>
          {api.diagnostics.map((d, i) => (
            <li key={`${i}-${d.message}`}>{d.message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** "Last synced 3 min ago", and whether this screen is showing the offline copy. */
export function SyncNote({ syncedAt, fromCache }: { syncedAt: number | null; fromCache: boolean }) {
  if (syncedAt === null && !fromCache) return null;
  return (
    <p className={`muted small ${styles.sync}`}>
      {fromCache ? "Offline copy · " : ""}
      {syncedAt !== null ? `Last synced ${agoLabel(syncedAt)}` : "Not synced yet"}
    </p>
  );
}
