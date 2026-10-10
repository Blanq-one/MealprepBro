import styles from "./Chips.module.css";

export type Chip = { key: string; label: string };

/** Rounded labels; ✕ removes one (pantry extras, suggestions, filters). Each is a 48 px target around a
 * 40 px pill. */
export function Chips({ chips, onRemove, onPick, label }: { chips: readonly Chip[]; onRemove?: (key: string) => void; onPick?: (key: string) => void; label: string }) {
  if (chips.length === 0) return null;
  return (
    <ul className={styles.chips} aria-label={label}>
      {chips.map((chip) => (
        <li key={chip.key} className={styles.item}>
          {onPick ? (
            <button type="button" className={styles.pill} onClick={() => onPick(chip.key)}>
              {chip.label}
            </button>
          ) : (
            <span className={styles.pill}>{chip.label}</span>
          )}
          {onRemove && (
            <button type="button" className={styles.remove} aria-label={`Remove ${chip.label}`} onClick={() => onRemove(chip.key)}>
              ✕
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
