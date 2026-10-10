import type { ReactNode } from "react";

import styles from "./ToggleRow.module.css";

/** A label (and badges) with a switch on the right: pantry items, Always-have staples, held items. */
export function ToggleRow({
  label,
  detail,
  badges,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  detail?: ReactNode;
  badges?: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className={styles.row}>
      <div className={styles.text}>
        <span className={styles.label}>{label}</span>
        {badges && <span className={styles.badges}>{badges}</span>}
        {detail && <span className="small muted">{detail}</span>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        className={checked ? `${styles.switch} ${styles.on}` : styles.switch}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span className={styles.knob} aria-hidden="true" />
      </button>
    </div>
  );
}
