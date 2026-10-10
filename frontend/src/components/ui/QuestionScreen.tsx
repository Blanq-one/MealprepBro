import type { ReactNode } from "react";

import styles from "./QuestionScreen.module.css";

/** One question per screen (FLOW_SPEC §5.1): back arrow, progress dots, Skip only if optional, the question,
 * a one-line why, one large control (onboarding may pair two), and a fixed bottom button. */
export function QuestionScreen({
  title,
  why,
  progress,
  onBack,
  onSkip,
  primaryLabel,
  onPrimary,
  primaryDisabled,
  busy,
  footerNote,
  secondary,
  reasons,
  children,
}: {
  title: string;
  why?: string;
  progress?: { step: number; total: number };
  onBack?: () => void;
  onSkip?: () => void;
  primaryLabel: string;
  onPrimary: () => void;
  primaryDisabled?: boolean;
  busy?: boolean;
  footerNote?: ReactNode;
  secondary?: ReactNode;
  /** Why Continue is disabled, or what the server said (shown under the control). */
  reasons?: readonly string[];
  children: ReactNode;
}) {
  return (
    <div className={styles.screen}>
      <div className={styles.top}>
        {onBack ? (
          <button type="button" className={styles.back} onClick={onBack} aria-label="Back">
            ←
          </button>
        ) : (
          <span className={styles.spacer} />
        )}
        {progress ? (
          <span className={styles.dots} role="img" aria-label={`Step ${progress.step} of ${progress.total}`}>
            {Array.from({ length: progress.total }, (_, i) => (
              <span key={i} className={i < progress.step ? `${styles.dot} ${styles.dotOn}` : styles.dot} />
            ))}
          </span>
        ) : (
          <span />
        )}
        {onSkip ? (
          <button type="button" className={styles.skip} onClick={onSkip}>
            Skip
          </button>
        ) : (
          <span className={styles.spacer} />
        )}
      </div>
      <h1 className={styles.title}>{title}</h1>
      {why && <p className={styles.why}>{why}</p>}
      <div className={styles.body}>{children}</div>
      {reasons && reasons.length > 0 && (
        <ul className={styles.reasons} role="alert">
          {reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      <div className={styles.footer}>
        <div className={styles.footerInner}>
          {secondary}
          <button type="button" className={`btn btn-primary btn-block ${styles.primary}`} onClick={onPrimary} disabled={primaryDisabled || busy}>
            {busy ? "Saving…" : primaryLabel}
          </button>
          {footerNote && <p className={styles.note}>{footerNote}</p>}
        </div>
      </div>
    </div>
  );
}
