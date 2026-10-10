"use client";

import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import type { SettingsOut } from "@/lib/api/types";
import { clockTime } from "@/lib/format/dates";
import { latestSync } from "@/lib/offline/lastSynced";
import { appQueue, type Conflict } from "@/lib/offline/queue";
import { applyTheme, followSystemTheme, readThemeChoice } from "@/lib/theme/theme";

import { BottomNav, showsTabs } from "./BottomNav";
import styles from "./AppShell.module.css";

function registerServiceWorker(): void {
  if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
  const local = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  if (window.location.protocol !== "https:" && !local) return; // iOS runs service workers over HTTPS only
  navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
    // no offline support this time; the app still works online
  });
}

export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

function useQueueState(online: boolean): { pending: number; conflicts: Conflict[]; dismiss: () => void } {
  const [pending, setPending] = useState(0);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  useEffect(() => {
    const queue = appQueue();
    const update = () => {
      setPending(queue.entries().length);
      setConflicts(queue.conflicts());
    };
    update();
    const unsubscribe = queue.subscribe(update);
    if (online) void queue.replay();
    return unsubscribe;
  }, [online]);
  return {
    pending,
    conflicts,
    dismiss: () => appQueue().clearConflicts(),
  };
}

let onboardingChecked = false;

/** On launch, the wizard runs if your settings say onboarding isn't done yet (FLOW_SPEC §6). Checked once
 * per app start; a failed check (offline, signed out) just skips it. */
function useOnboardingGate(pathname: string): void {
  const router = useRouter();
  useEffect(() => {
    if (onboardingChecked || pathname.startsWith("/login") || pathname.startsWith("/welcome")) return;
    onboardingChecked = true;
    fetch("/api/v1/settings", { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then((response) => (response.ok ? (response.json() as Promise<SettingsOut>) : null))
      .then((body) => {
        if (body && body.settings.onboarding_completed === false) router.replace("/welcome/");
      })
      .catch(() => undefined);
  }, [pathname, router]);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const online = useOnline();
  const { pending, conflicts, dismiss } = useQueueState(online);
  const showNav = showsTabs(pathname);
  const [syncedAt, setSyncedAt] = useState<number | null>(null);

  useEffect(registerServiceWorker, []);
  useEffect(() => {
    applyTheme(readThemeChoice());
    return followSystemTheme();
  }, []);
  useEffect(() => {
    if (!online) setSyncedAt(latestSync());
  }, [online, pathname]);
  useOnboardingGate(pathname);

  return (
    <div className={styles.shell}>
      {!online && (
        <div className={styles.banner} role="status">
          You&apos;re offline{syncedAt !== null ? ` · showing what was saved at ${clockTime(syncedAt)}` : ""}.
          {pending > 0 && ` ${pending} change${pending === 1 ? "" : "s"} will sync when you're back online.`}
        </div>
      )}
      {online && pending > 0 && (
        <div className={styles.banner} role="status">
          Syncing {pending} change{pending === 1 ? "" : "s"}…
        </div>
      )}
      {conflicts.length > 0 && (
        <div className={`${styles.banner} ${styles.conflict}`} role="alert">
          <div>
            {conflicts.length === 1 ? "A change" : `${conflicts.length} changes`} made offline couldn&apos;t be
            saved:
            <ul className={styles.conflictList}>
              {conflicts.map((c) => (
                <li key={c.entry.client_ref}>
                  {c.entry.label ?? `${c.entry.method} ${c.entry.url}`}: {c.title}
                  {c.detail ? ` (${c.detail})` : ""}
                </li>
              ))}
            </ul>
          </div>
          <button type="button" className="btn btn-small" onClick={dismiss}>
            OK
          </button>
        </div>
      )}
      <main className={showNav ? styles.main : styles.mainBare}>{children}</main>
      {showNav && <BottomNav pathname={pathname} />}
    </div>
  );
}
