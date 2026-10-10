import styles from "./Pottle.module.css";

export type PottleState = "idle" | "working" | "happy" | "sleepy" | "oops";

const LABELS: Record<PottleState, string> = {
  idle: "Pottle the clay pot",
  working: "Pottle, busy cooking",
  happy: "Pottle, happy",
  sleepy: "Pottle, asleep",
  oops: "Pottle, surprised",
};

function Steam({ state }: { state: PottleState }) {
  switch (state) {
    case "working":
      return (
        <g className={`${styles.steam} ${styles.rising}`}>
          <path d="M23 16c-3-2.5 3-5 0-8.5" />
          <path d="M32 15c-3.5-3 3.5-6 0-10" />
          <path d="M41 16c-3-2.5 3-5 0-8.5" />
        </g>
      );
    case "happy":
      return (
        <path
          className={styles.heart}
          d="M32 16c-5.5-3.6-7.5-6.6-7.5-9.2 0-2.2 1.7-3.8 3.7-3.8 1.6 0 3 .9 3.8 2.3.8-1.4 2.2-2.3 3.8-2.3 2 0 3.7 1.6 3.7 3.8 0 2.6-2 5.6-7.5 9.2z"
        />
      );
    case "sleepy":
      return (
        <g className={styles.steam}>
          <path d="M28 15c-3-2.5 3-4.5 0-7.5" />
          <path d="M37 9h6l-6 6h6" />
        </g>
      );
    case "oops":
      return (
        <g className={styles.steam}>
          <path d="M33 14c-4-3 4-5.5 0-10" />
        </g>
      );
    default:
      return (
        <g className={styles.steam}>
          <path d="M32 15c-4-3 4-5.5 0-10" />
        </g>
      );
  }
}

/** Pottle, the app's clay-pot character (FLOW_SPEC §4.1): a few inline shapes, the steam shows the state. */
export function Pottle({ state = "idle", size = 64, decorative = false }: { state?: PottleState; size?: number; decorative?: boolean }) {
  const lid =
    state === "sleepy" ? "rotate(-10 32 27)" : state === "oops" ? "translate(2 -3) rotate(12 32 27)" : undefined;
  const wide = state === "oops";
  return (
    <svg
      className={styles.pottle}
      viewBox="0 0 64 64"
      width={size}
      height={size}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : LABELS[state]}
      aria-hidden={decorative ? true : undefined}
      data-state={state}
    >
      <Steam state={state} />
      <g transform={lid}>
        <path className={styles.lid} d="M13.5 30c0-6 8.3-9.5 18.5-9.5S50.5 24 50.5 30z" />
        <circle className={styles.lid} cx="32" cy="19.5" r="3.2" />
      </g>
      <rect className={styles.rim} x="9" y="29.5" width="46" height="6" rx="3" />
      <path className={styles.body} d="M11.5 35h41c0 14.5-7 23-20.5 23S11.5 49.5 11.5 35z" />
      {state === "sleepy" ? (
        <>
          <path className={styles.mouth} d="M22.5 43q2.5 2 5 0M36.5 43q2.5 2 5 0" />
          <path className={styles.mouth} d="M29.5 49.5q2.5 1.5 5 0" />
        </>
      ) : (
        <>
          <circle className={styles.face} cx="25" cy="43" r={wide ? 2.6 : 2.1} />
          <circle className={styles.face} cx="39" cy="43" r={wide ? 2.6 : 2.1} />
        </>
      )}
      {state === "sleepy" ? null : state === "oops" ? (
        <circle className={styles.mouthO} cx="32" cy="50" r="2" />
      ) : (
        <path className={styles.mouth} d={state === "happy" ? "M27 48q5 5 10 0" : "M28 48.5q4 3.5 8 0"} />
      )}
    </svg>
  );
}
