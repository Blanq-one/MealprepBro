"use client";

import { type ReactNode, useEffect, useId, useRef } from "react";

import styles from "./BottomSheet.module.css";

/** Slides up from the bottom with a grabber; one task (amount picker, confirmations). Closes on the backdrop,
 * Escape, or its own buttons. */
export function BottomSheet({ title, open, onClose, children }: { title: string; open: boolean; onClose: () => void; children: ReactNode }) {
  const id = useId();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className={styles.layer}>
      <button type="button" className={styles.backdrop} aria-label="Close" tabIndex={-1} onClick={onClose} />
      <div ref={panel} className={styles.sheet} role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} tabIndex={-1}>
        <span className={styles.grabber} aria-hidden="true" />
        <h2 id={`${id}-title`} className={styles.title}>
          {title}
        </h2>
        {children}
      </div>
    </div>
  );
}
