"use client";

import { type PointerEvent, useEffect, useId, useRef, useState } from "react";

import { grouped } from "@/lib/format/labels";

import styles from "./Stepper.module.css";

const HOLD_DELAY_MS = 400;
const HOLD_EVERY_MS = 90;

export type StepperProps = {
  label: string;
  value: number | null; // null = not set yet ("a newly added meal starts empty")
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
  unit?: string;
  /** Shown instead of the number (e.g. 0 -> "No target"). Plain formatting only. */
  format?: (value: number) => string;
  /** Typing allows decimals (custom amounts), else whole numbers only. */
  decimal?: boolean;
  disabled?: boolean;
  /** Visually hide the label (a paired screen names the control in its own heading). */
  hideLabel?: boolean;
  size?: "large" | "compact";
};

function decimalsOf(step: number): number {
  const text = String(step);
  return text.includes(".") ? (text.split(".")[1]?.length ?? 0) : 0;
}

/** The value one step up or down, kept inside the bounds. Rounded to the step's decimals so 0.1 + 0.2 shows
 * as 0.3 (this is input handling: the server does every conversion and every calculation). */
export function stepValue(value: number | null, direction: 1 | -1, { min, max, step }: Pick<StepperProps, "min" | "max" | "step">): number {
  if (value === null) return min;
  const next = Number((value + direction * step).toFixed(decimalsOf(step)));
  return Math.min(max, Math.max(min, next));
}

export function inRange(value: number | null, min: number, max: number): boolean {
  return value !== null && Number.isFinite(value) && value >= min && value <= max;
}

export function rangeReason(label: string, min: number, max: number, unit?: string): string {
  return `${label}: pick from ${grouped(min)} to ${grouped(max)}${unit ? ` ${unit}` : ""}.`;
}

/** 64 px − and + around a large value. Tap steps by the field's increment, press and hold repeats, and a
 * tap on the value types it (numeric keypad). */
export function Stepper({
  label,
  value,
  onChange,
  min,
  max,
  step,
  unit,
  format,
  decimal = false,
  disabled = false,
  hideLabel = false,
  size = "large",
}: StepperProps) {
  const id = useId();
  const latest = useRef(value);
  latest.current = value;
  const timers = useRef<{ delay?: ReturnType<typeof setTimeout>; every?: ReturnType<typeof setInterval> }>({});
  const held = useRef(false); // a press that repeated: its click doesn't step once more
  const [typing, setTyping] = useState<string | null>(null);

  useEffect(() => stopHold, []);

  function stopHold() {
    clearTimeout(timers.current.delay);
    clearInterval(timers.current.every);
    timers.current = {};
  }

  function bump(direction: 1 | -1) {
    const next = stepValue(latest.current, direction, { min, max, step });
    if (next === latest.current) {
      // at a bound: the button turns disabled and never sees the finger lift
      stopHold();
      held.current = false;
      return;
    }
    latest.current = next;
    onChange(next);
  }

  // A tap (click, Enter, Space, VoiceOver) steps once; holding a finger down repeats until it lifts.
  function startHold(direction: 1 | -1, event: PointerEvent<HTMLButtonElement>) {
    if (disabled || event.button > 0) return; // not a secondary mouse button
    stopHold();
    held.current = false;
    timers.current.delay = setTimeout(() => {
      held.current = true;
      bump(direction);
      timers.current.every = setInterval(() => bump(direction), HOLD_EVERY_MS);
    }, HOLD_DELAY_MS);
  }

  function tap(direction: 1 | -1) {
    stopHold();
    if (held.current) {
      held.current = false;
      return;
    }
    bump(direction);
  }

  function commitTyping() {
    if (typing === null) return;
    const text = typing.trim().replace(/,/g, "");
    const pattern = decimal ? /^\d+(\.\d+)?$/ : /^\d+$/;
    if (pattern.test(text)) onChange(Number(text));
    setTyping(null);
  }

  const atMin = value !== null && value <= min;
  const atMax = value !== null && value >= max;
  const shown = value === null ? "—" : format ? format(value) : grouped(value);
  const outOfRange = value !== null && !inRange(value, min, max);

  return (
    <div className={size === "compact" ? `${styles.stepper} ${styles.compact}` : styles.stepper} role="group" aria-labelledby={`${id}-label`}>
      <span id={`${id}-label`} className={hideLabel ? "sr-only" : styles.label}>
        {label}
      </span>
      <div className={styles.controls}>
        <button
          type="button"
          className={styles.round}
          aria-label={`Less ${label.toLowerCase()}`}
          disabled={disabled || atMin || value === null}
          onPointerDown={(e) => startHold(-1, e)}
          onPointerUp={stopHold}
          onPointerLeave={stopHold}
          onPointerCancel={stopHold}
          onClick={() => tap(-1)}
          onContextMenu={(e) => e.preventDefault()}
        >
          −
        </button>
        <div className={styles.middle}>
          {typing !== null ? (
            <input
              className={styles.typed}
              aria-label={`${label}, type a number`}
              inputMode={decimal ? "decimal" : "numeric"}
              value={typing}
              autoFocus
              onChange={(e) => setTyping(e.target.value)}
              onBlur={commitTyping}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitTyping();
                if (e.key === "Escape") setTyping(null);
              }}
            />
          ) : (
            <button
              type="button"
              className={styles.value}
              aria-label={`${label}: ${shown}${unit && format === undefined && value !== null ? ` ${unit}` : ""}. Tap to type a number`}
              disabled={disabled}
              onClick={() => setTyping(value === null ? "" : String(value))}
            >
              <output aria-live="polite">{shown}</output>
            </button>
          )}
          {unit && <span className={styles.unit}>{unit}</span>}
        </div>
        <button
          type="button"
          className={styles.round}
          aria-label={`More ${label.toLowerCase()}`}
          disabled={disabled || atMax}
          onPointerDown={(e) => startHold(1, e)}
          onPointerUp={stopHold}
          onPointerLeave={stopHold}
          onPointerCancel={stopHold}
          onClick={() => tap(1)}
          onContextMenu={(e) => e.preventDefault()}
        >
          +
        </button>
      </div>
      {outOfRange && (
        <p className={styles.reason} role="alert">
          {rangeReason(label, min, max, unit)}
        </p>
      )}
    </div>
  );
}
