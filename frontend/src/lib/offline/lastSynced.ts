// "Last synced": when each screen's data last came from the server (not from the offline cache).

const PREFIX = "mealbro.synced.";

export function markSynced(key: string, at: number = Date.now()): void {
  try {
    localStorage.setItem(PREFIX + key, String(at));
  } catch {
    // private mode or storage blocked: the indicator just won't show
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
