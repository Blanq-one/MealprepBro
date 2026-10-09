// The offline queue (Q18): grocery check-offs and price entries made without a connection wait here and are
// replayed, in order, once the app is online again.
//
// Each entry has a client_ref. A price entry carries it in its body, so the server stores it exactly once
// even if a replay is interrupted after the server saw it; check-offs are PATCHes that set values, so
// replaying one changes nothing. On replay: 2xx -> done; 4xx (except 401, 408, 429) -> dropped and shown as a
// conflict; anything else (no network, 5xx, 401, 408, 429) -> kept, and replay stops so the order holds.

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export type QueuedRequest = {
  client_ref: string;
  method: "POST" | "PATCH" | "PUT" | "DELETE";
  url: string;
  body?: Record<string, unknown>;
  label?: string; // what the user did, for the conflict message ("Check off chicken thigh")
  createdAt: number;
};

export type Conflict = { entry: QueuedRequest; status: number; title: string; detail: string };

export type SendResult = { status: number; title?: string; detail?: string };
/** Sends one entry; throws when the network is unreachable. */
export type Sender = (entry: QueuedRequest) => Promise<SendResult>;

export type ReplayResult = { sent: number; conflicts: Conflict[]; kept: number };

export type EnqueueInput = Omit<QueuedRequest, "client_ref" | "createdAt"> & {
  client_ref?: string;
  refInBody?: boolean; // put client_ref into the body as well (price entries)
};

const KEEP_STATUSES = new Set([401, 408, 429]);

export class MemoryStorage implements KeyValueStorage {
  private data = new Map<string, string>();
  getItem(key: string): string | null {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }
  setItem(key: string, value: string): void {
    this.data.set(key, value);
  }
  removeItem(key: string): void {
    this.data.delete(key);
  }
}

export const fetchSender: Sender = async (entry) => {
  const response = await fetch(entry.url, {
    method: entry.method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: entry.body !== undefined ? JSON.stringify(entry.body) : undefined,
  });
  if (response.ok) return { status: response.status };
  let title = response.statusText;
  let detail = "";
  try {
    const problem = (await response.json()) as { title?: string; detail?: string };
    title = problem.title ?? title;
    detail = problem.detail ?? "";
  } catch {
    // not JSON: keep the status text
  }
  return { status: response.status, title, detail };
};

function newRef(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // RFC 4122 v4 from getRandomValues (older browsers)
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export class OfflineQueue {
  private running: Promise<ReplayResult> | null = null;
  private listeners = new Set<() => void>();

  constructor(
    private readonly storage: KeyValueStorage,
    private readonly send: Sender = fetchSender,
    private readonly key = "mealbro.queue",
  ) {}

  entries(): QueuedRequest[] {
    return this.read<QueuedRequest[]>(this.key, []);
  }

  conflicts(): Conflict[] {
    return this.read<Conflict[]>(`${this.key}.conflicts`, []);
  }

  clearConflicts(): void {
    this.storage.removeItem(`${this.key}.conflicts`);
    this.notify();
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Add a request to the end of the queue (it is sent on the next replay). */
  enqueue(input: EnqueueInput): QueuedRequest {
    const { refInBody, client_ref, ...rest } = input;
    const ref = client_ref ?? newRef();
    const entry: QueuedRequest = {
      ...rest,
      client_ref: ref,
      body: refInBody ? { ...(rest.body ?? {}), client_ref: ref } : rest.body,
      createdAt: Date.now(),
    };
    this.write(this.key, [...this.entries(), entry]);
    this.notify();
    return entry;
  }

  /** Send queued requests in order. Only one replay runs at a time. */
  replay(): Promise<ReplayResult> {
    if (this.running) return this.running;
    this.running = this.drain().finally(() => {
      this.running = null;
    });
    return this.running;
  }

  private async drain(): Promise<ReplayResult> {
    let sent = 0;
    const conflicts: Conflict[] = [];
    for (;;) {
      const [entry] = this.entries();
      if (!entry) break;
      let result: SendResult;
      try {
        result = await this.send(entry);
      } catch {
        break; // offline: keep it and stop, so later entries don't overtake it
      }
      if (result.status >= 200 && result.status < 300) {
        sent += 1;
      } else if (result.status >= 400 && result.status < 500 && !KEEP_STATUSES.has(result.status)) {
        const conflict = {
          entry,
          status: result.status,
          title: result.title ?? "Rejected",
          detail: result.detail ?? "",
        };
        conflicts.push(conflict);
        this.write(`${this.key}.conflicts`, [...this.conflicts(), conflict]);
      } else {
        break; // server trouble, signed out or rate limited: try again later
      }
      this.write(
        this.key,
        this.entries().filter((e) => e.client_ref !== entry.client_ref),
      );
      this.notify();
    }
    return { sent, conflicts, kept: this.entries().length };
  }

  private read<T>(key: string, fallback: T): T {
    try {
      const raw = this.storage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : fallback;
    } catch {
      return fallback;
    }
  }

  private write(key: string, value: unknown): void {
    try {
      this.storage.setItem(key, JSON.stringify(value));
    } catch {
      // storage full or blocked: the queue lives in memory for this page only
    }
  }

  private notify(): void {
    for (const listener of this.listeners) listener();
  }
}

let shared: OfflineQueue | null = null;

/** The app's queue, kept in localStorage. */
export function appQueue(): OfflineQueue {
  if (!shared) {
    let storage: KeyValueStorage;
    try {
      storage = window.localStorage;
      storage.getItem("mealbro.probe");
    } catch {
      storage = new MemoryStorage();
    }
    shared = new OfflineQueue(storage);
  }
  return shared;
}
