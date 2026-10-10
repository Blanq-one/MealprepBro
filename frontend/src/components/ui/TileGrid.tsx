import type { ReactNode } from "react";

import styles from "./TileGrid.module.css";

export type Tile = { key: string; label: string; icon?: ReactNode; hint?: string; disabled?: boolean };

/** Two columns of 96 px tiles. Selected = accent fill, a check (or its order number) and aria-pressed. */
export function TileGrid({
  label,
  tiles,
  selected,
  onToggle,
  order,
  notice,
}: {
  label: string;
  tiles: readonly Tile[];
  selected: readonly string[];
  onToggle: (key: string) => void;
  /** Show the order a tile was picked in (1, 2…) instead of a check. */
  order?: boolean;
  /** Why a tap didn't do what you expected (a limit you hit). */
  notice?: string | null;
}) {
  return (
    <div>
      <div className={styles.grid} role="group" aria-label={label}>
        {tiles.map((tile) => {
          const index = selected.indexOf(tile.key);
          const on = index >= 0;
          return (
            <button
              key={tile.key}
              type="button"
              className={on ? `${styles.tile} ${styles.on}` : styles.tile}
              aria-pressed={on}
              disabled={tile.disabled}
              onClick={() => onToggle(tile.key)}
            >
              {on && (
                <span className={styles.badge} aria-hidden="true">
                  {order ? String(index + 1) : "✓"}
                </span>
              )}
              {tile.icon && (
                <span className={styles.icon} aria-hidden="true">
                  {tile.icon}
                </span>
              )}
              <span className={styles.label}>{tile.label}</span>
              {order && on && <span className="sr-only">, number {index + 1}</span>}
              {tile.hint && <span className={styles.hint}>{tile.hint}</span>}
            </button>
          );
        })}
      </div>
      {notice && (
        <p className={styles.notice} role="status">
          {notice}
        </p>
      )}
    </div>
  );
}
