"use client";

import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { appQueue, type Conflict } from "@/lib/offline/queue";

import { BottomNav } from "./BottomNav";
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

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const online = useOnline();
  const { pending, conflicts, dismiss } = useQueueState(online);
  const showNav = !pathname.startsWith("/login");

  useEffect(registerServiceWorker, []);

  return (
    <div className={styles.shell}>
      {!online && (
        <div className={styles.banner} role="status">
          Offline: showing what was saved on this phone.
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
