"use client";

import type { VersionChoice, Versions } from "@/lib/api/types";

import styles from "./AddFlow.module.css";

const STATE_BADGES: Record<VersionChoice["state"], { label: string; className: string }> = {
  allowed: { label: "Allowed", className: "badge badge-herb" },
  capped: { label: "Allowed, limited", className: "badge badge-accent" },
  held: { label: "Stays held", className: "badge badge-warn" },
  excluded: { label: "Off your list", className: "badge badge-danger" },
};

/** "Which pepperoni is it?" with the server's "Check the label" guidance, and each version with what it means
 * for your diet (J4). Every word is the server's. */
export function VersionChoices({
  versions,
  selected,
  onPick,
  disabled,
  usual,
}: {
  versions: Versions;
  selected: string | null;
  onPick: (choice: VersionChoice) => void;
  disabled?: boolean;
  /** Your usual version (Settings), marked so you can spot it. */
  usual?: string | null;
}) {
  return (
    <div className={styles.versions}>
      <p className={styles.question}>{versions.question}</p>
      <p className={`notice ${styles.guidance}`}>{versions.guidance}</p>
      <div role="group" aria-label={versions.question} className={styles.choiceList}>
        {versions.choices.map((choice) => {
          const badge = STATE_BADGES[choice.state];
          const on = choice.key === selected;
          return (
            <button
              key={choice.key}
              type="button"
              className={on ? `${styles.choice} ${styles.choiceOn}` : styles.choice}
              aria-pressed={on}
              disabled={disabled}
              onClick={() => onPick(choice)}
            >
              <span className={styles.choiceLabel}>
                {choice.label}
                {usual === choice.key && <span className="small muted"> · your usual</span>}
              </span>
              <span className={badge.className}>{badge.label}</span>
              <span className={styles.choiceNote}>
                {choice.note}
                {choice.nutrition_estimated ? " · nutrition estimated" : ""}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
