import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./client";
import { readNdjson, streamPlan } from "./ndjson";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

const lines = [
  { event: "started", run_id: 5, elapsed_s: 0, pad: "  " },
  { event: "progress", run_id: 5, elapsed_s: 1.2, stage: "solving", message: "Fitting the week together" },
  { event: "heartbeat", run_id: 5, elapsed_s: 6.2 },
  { event: "result", run_id: 5, elapsed_s: 9.9, status: "succeeded", plan_id: 12 },
];
const text = lines.map((l) => JSON.stringify(l)).join("\n") + "\n";

describe("readNdjson", () => {
  it("reads whole lines", async () => {
    const seen: unknown[] = [];
    expect(await readNdjson(streamOf([text]), (e) => seen.push(e))).toBe(4);
    expect(seen).toEqual(lines);
  });

  it("joins lines split across chunks at any point, including inside a multi-byte character", async () => {
    const withAccent = JSON.stringify({ event: "progress", run_id: 1, elapsed_s: 0, message: "Sauté – 425°F" }) + "\n";
    const bytes = new TextEncoder().encode(text + withAccent);
    const chunks: Uint8Array[] = [];
    for (let i = 0; i < bytes.length; i += 7) chunks.push(bytes.slice(i, i + 7));
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const c of chunks) controller.enqueue(c);
        controller.close();
      },
    });
    const seen: { message?: string }[] = [];
    await readNdjson<{ message?: string }>(stream, (e) => seen.push(e));
    expect(seen).toHaveLength(5);
    expect(seen[4]?.message).toBe("Sauté – 425°F");
  });

  it("reads a last line without a trailing newline and skips blank lines", async () => {
    const seen: unknown[] = [];
    await readNdjson(streamOf(['{"a":1}\n\n', '\n{"a":2}']), (e) => seen.push(e));
    expect(seen).toEqual([{ a: 1 }, { a: 2 }]);
  });
});

describe("streamPlan", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts the request and hands each event over", async () => {
    const fetchMock = vi.fn(async () => new Response(streamOf([text]), { status: 200, headers: { "content-type": "application/x-ndjson" } }));
    vi.stubGlobal("fetch", fetchMock);
    const events: { event: string }[] = [];
    await streamPlan({ week_start: "2026-10-12", mode: "shop" }, (e) => events.push(e));
    expect(events.map((e) => e.event)).toEqual(["started", "progress", "heartbeat", "result"]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/plans");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ week_start: "2026-10-12", mode: "shop" });
  });

  it("turns a refused request into an ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ title: "Invalid request", status: 422, detail: "The request did not pass validation." }), {
            status: 422,
            headers: { "content-type": "application/problem+json" },
          }),
      ),
    );
    await expect(streamPlan({ week_start: "x" }, () => undefined)).rejects.toBeInstanceOf(ApiError);
  });
});
