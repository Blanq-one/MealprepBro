// The version of a held item you usually buy (Settings' held items, J4), kept on this device. It only
// pre-selects that version when you add the item; it never allows the generic held item.
const KEY = "mealbro.usual-versions";

type Store = Pick<Storage, "getItem" | "setItem">;

function local(): Store | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function usualVersions(storage: Store | null = local()): Record<string, string> {
  try {
    const raw = storage?.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : null;
    return parsed && typeof parsed === "object" ? (parsed as Record<string, string>) : {};
  } catch {
    return {};
  }
}

/** Remember (or with null forget) the usual version of a held item, by the item's ingredient id. */
export function setUsualVersion(heldId: number, key: string | null, storage: Store | null = local()): Record<string, string> {
  const next = { ...usualVersions(storage) };
  if (key === null) delete next[String(heldId)];
  else next[String(heldId)] = key;
  try {
    storage?.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage blocked: nothing is remembered
  }
  return next;
}
