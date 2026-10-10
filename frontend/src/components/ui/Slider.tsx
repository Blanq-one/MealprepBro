"use client";

import { useId } from "react";

import { formatCents } from "@/lib/format/money";

import styles from "./Slider.module.css";

/** Slider positions in cents. `noLimitAt` is the extra position at the right end that means "no limit". */
export type MoneyScale = { min: number; max: number; step: number; noLimitAt?: number };

/** The budget: $0–$200 in $5 steps, "No limit" at the end (FLOW_SPEC §5.2). */
export const BUDGET_SCALE: MoneyScale = { min: 0, max: 20_000, step: 500, noLimitAt: 20_500 };

/** A money slider. The browser's range input does the stepping; the app only formats cents. */
export function MoneySlider({
  label,
  valueCents,
  onChange,
  scale,
  disabled,
  hideLabel,
}: {
  label: string;
  valueCents: number | null;
  onChange: (cents: number | null) => void;
  scale: MoneyScale;
  disabled?: boolean;
  hideLabel?: boolean;
}) {
  const id = useId();
  const top = scale.noLimitAt ?? scale.max;
  const position = valueCents === null ? top : Math.min(valueCents, scale.max);
  const shown = valueCents === null ? "No limit" : formatCents(valueCents);
  return (
    <div className={styles.slider}>
      <label htmlFor={id} className={hideLabel ? "sr-only" : styles.label}>
        {label}
      </label>
      <output htmlFor={id} className={styles.value} aria-live="polite">
        {shown}
      </output>
      <input
        id={id}
        type="range"
        className={styles.range}
        min={scale.min}
        max={top}
        step={scale.step}
        value={position}
        disabled={disabled}
        aria-valuetext={shown}
        onChange={(e) => {
          const cents = Number(e.target.value);
          onChange(scale.noLimitAt !== undefined && cents === scale.noLimitAt ? null : cents);
        }}
      />
      <div className={styles.ends} aria-hidden="true">
        <span>{formatCents(scale.min)}</span>
        <span>{scale.noLimitAt !== undefined ? "No limit" : formatCents(scale.max)}</span>
      </div>
    </div>
  );
}
