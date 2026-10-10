import styles from "./Segmented.module.css";

export type Segment<T extends string> = { value: T; label: string };

/** 2–5 equal buttons in a pill. The chosen one is accent-filled with a check, bold, and aria-pressed (the
 * fixed selected state, FLOW_SPEC §11). */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  disabled,
}: {
  label: string;
  options: readonly Segment<T>[];
  value: T | null;
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <div className={styles.segmented} role="group" aria-label={label}>
      {options.map((option) => {
        const on = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            className={on ? `${styles.segment} ${styles.on}` : styles.segment}
            aria-pressed={on}
            disabled={disabled}
            onClick={() => onChange(option.value)}
          >
            {on && (
              <span className={styles.check} aria-hidden="true">
                ✓
              </span>
            )}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
