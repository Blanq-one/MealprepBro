// "Last synced": when each screen's data last came from the server (not from the offline cache).

const PREFIX = "mealbro.synced.";

export function markSynced(key: string, at: number = Date.now()): void {
  try {
    localStorage.setItem(PREFIX + key, String(at));
  } catch {
    // private mode or storage blocked: the indicator just won't show
  }
}

/** The most recent sync of any screen (the offline banner's "showing what was saved at 3:42 pm"). */
export function latestSync(): number | null {
  try {
    let latest: number | null = null;
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (!key?.startsWith(PREFIX)) continue;
      const at = lastSynced(key.slice(PREFIX.length));
      if (at !== null && (latest === null || at > latest)) latest = at;
    }
    return latest;
  } catch {
    return null;
  }
}

export function lastSynced(key: string): number | null {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw && /^\d+$/.test(raw) ? Number(raw) : null;
  } catch {
    return null;
  }
}
