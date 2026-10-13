// A stub for the API in component tests: every fetch is recorded and answered by `reply`. A reply with `lines`
// is an NDJSON stream (one JSON value a line), like the streamed endpoints.
import { vi } from "vitest";

export type Call = { method: string; path: string; body: unknown };
export type Reply = { status?: number; body?: unknown; lines?: unknown[] } | undefined;

export function mockApi(reply: (call: Call) => Reply): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const call: Call = {
        method: (init.method ?? "GET").toUpperCase(),
        path: url,
        body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
      };
      calls.push(call);
      const answer = reply(call) ?? { status: 404, body: { title: "Not found", detail: url } };
      const status = answer.status ?? 200;
      if (answer.lines) {
        const text = answer.lines.map((l) => JSON.stringify(l)).join("\n") + "\n";
        return new Response(text, { status, headers: { "content-type": "application/x-ndjson" } });
      }
      return new Response(status === 204 ? null : JSON.stringify(answer.body ?? null), {
        status,
        headers: { "content-type": status >= 400 ? "application/problem+json" : "application/json" },
      });
    }),
  );
  return calls;
}
