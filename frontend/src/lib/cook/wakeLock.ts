// Cooking mode keeps the screen awake (C8) with the browser's Wake Lock, where the phone offers it. The lock
// drops when the page is hidden, so it is asked for again when you come back.
import { useEffect, useState } from "react";

type Sentinel = { release: () => Promise<void> };
type WakeLockApi = { request: (type: "screen") => Promise<Sentinel> };

function wakeLockApi(): WakeLockApi | null {
  if (typeof navigator === "undefined") return null;
  const api = (navigator as Navigator & { wakeLock?: WakeLockApi }).wakeLock;
  return api ?? null;
}

/** "on" while the screen is kept awake, "unsupported" where the browser can't, "off" otherwise. */
export function useWakeLock(active: boolean): "on" | "off" | "unsupported" {
  const [state, setState] = useState<"on" | "off" | "unsupported">(() => (wakeLockApi() ? "off" : "unsupported"));
  useEffect(() => {
    const api = wakeLockApi();
    if (!api || !active) return;
    let sentinel: Sentinel | null = null;
    let stopped = false;
    const take = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const next = await api.request("screen");
        if (stopped) {
          void next.release();
          return;
        }
        sentinel = next;
        setState("on");
      } catch {
        setState("off"); // battery saver or a denied permission: cooking mode still works
      }
    };
    const onVisible = () => void take();
    void take();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      document.removeEventListener("visibilitychange", onVisible);
      void sentinel?.release().catch(() => undefined);
      setState("off");
    };
  }, [active]);
  return state;
}
