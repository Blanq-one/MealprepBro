"use client";

// Plain fetch hook for GETs. The service worker answers from its cache when offline and marks those
// responses with `x-mealbro-cache: hit`, so a screen can say its data is from the last sync.
import { useCallback, useEffect, useRef, useState } from "react";

import { problemFrom, redirectToLogin } from "@/lib/api/client";
import { lastSynced, markSynced } from "@/lib/offline/lastSynced";

export const CACHE_HEADER = "x-mealbro-cache";

export type ApiState<T> = {
  data: T | null;
  error: unknown;
  loading: boolean;
  fromCache: boolean;
  syncedAt: number | null;
  reload: () => Promise<void>;
  setData: (data: T) => void;
};

export function useApi<T>(path: string | null): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const [fromCache, setFromCache] = useState(false);
  const [syncedAt, setSyncedAt] = useState<number | null>(null);
  const current = useRef(path);
  current.current = path;

  const load = useCallback(async () => {
    if (path === null) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(path, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok) {
        const problem = await problemFrom(response);
        if (response.status === 401) redirectToLogin();
        throw problem;
      }
      const body = (await response.json()) as T;
      if (current.current !== path) return;
      const cached = response.headers.get(CACHE_HEADER) === "hit";
      if (!cached) markSynced(path);
      setData(body);
      setFromCache(cached);
      setSyncedAt(lastSynced(path));
      setError(null);
    } catch (e) {
      if (current.current === path) {
        setError(e);
        setSyncedAt(lastSynced(path));
      }
    } finally {
      if (current.current === path) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, error, loading, fromCache, syncedAt, reload: load, setData };
}
