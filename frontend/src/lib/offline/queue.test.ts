import { describe, expect, it } from "vitest";

import { MemoryStorage, OfflineQueue, type QueuedRequest, type Sender } from "./queue";

function recorder(statuses: (number | "offline")[]) {
  const sent: QueuedRequest[] = [];
  const send: Sender = async (entry) => {
    const next = statuses.shift() ?? 200;
    if (next === "offline") throw new TypeError("Failed to fetch");
    sent.push(entry);
    return { status: next, title: next >= 400 ? "Conflict" : undefined, detail: next >= 400 ? "this trip is already done" : undefined };
  };
  return { sent, send };
}

const patch = (id: number) => ({ method: "PATCH" as const, url: `/api/v1/grocery-items/${id}`, body: { checked: true } });

describe("OfflineQueue", () => {
  it("keeps entries in order with a client_ref each, and survives a reload of the page", () => {
    const storage = new MemoryStorage();
    const queue = new OfflineQueue(storage, recorder([]).send);
    const a = queue.enqueue(patch(1));
    const b = queue.enqueue(patch(2));
    expect(a.client_ref).toMatch(/^[0-9a-f-]{36}$/);
    expect(a.client_ref).not.toBe(b.client_ref);
    const reloaded = new OfflineQueue(storage, recorder([]).send);
    expect(reloaded.entries().map((e) => e.url)).toEqual(["/api/v1/grocery-items/1", "/api/v1/grocery-items/2"]);
  });

  it("replays in order and empties the queue", async () => {
    const { sent, send } = recorder([200, 200, 200]);
    const queue = new OfflineQueue(new MemoryStorage(), send);
    queue.enqueue(patch(1));
    queue.enqueue(patch(2));
    queue.enqueue(patch(3));
    const result = await queue.replay();
    expect(sent.map((e) => e.url)).toEqual([
      "/api/v1/grocery-items/1",
      "/api/v1/grocery-items/2",
      "/api/v1/grocery-items/3",
    ]);
    expect(result).toEqual({ sent: 3, conflicts: [], kept: 0 });
    expect(queue.entries()).toEqual([]);
  });

  it("puts the client_ref in the body of a price entry, and sends that same ref on every replay", async () => {
    const { sent, send } = recorder(["offline", 201]);
    const queue = new OfflineQueue(new MemoryStorage(), send);
    const entry = queue.enqueue({
      method: "POST",
      url: "/api/v1/prices",
      body: { product_id: 4, store_id: 1, price_cents: 199, per_amount: 1, per_unit: "lb", observed_on: "2026-10-12" },
      refInBody: true,
    });
    expect(entry.body?.client_ref).toBe(entry.client_ref);
    expect((await queue.replay()).kept).toBe(1); // offline: kept
    expect((await queue.replay()).sent).toBe(1);
    expect(sent[0]?.body?.client_ref).toBe(entry.client_ref);
  });

  it("drops a rejected entry, surfaces it as a conflict and carries on", async () => {
    const { sent, send } = recorder([409, 200]);
    const queue = new OfflineQueue(new MemoryStorage(), send);
    queue.enqueue({ ...patch(1), label: "Check off chicken" });
    queue.enqueue(patch(2));
    const result = await queue.replay();
    expect(result.sent).toBe(1);
    expect(result.conflicts).toHaveLength(1);
    expect(queue.conflicts()[0]).toMatchObject({ status: 409, title: "Conflict", detail: "this trip is already done" });
    expect(queue.conflicts()[0]?.entry.label).toBe("Check off chicken");
    expect(sent).toHaveLength(2);
    queue.clearConflicts();
    expect(queue.conflicts()).toEqual([]);
  });

  it("keeps everything on a network error or a server problem, and stops so nothing overtakes it", async () => {
    for (const failure of ["offline", 500, 429, 408, 401] as const) {
      const { sent, send } = recorder([failure, 200]);
      const queue = new OfflineQueue(new MemoryStorage(), send);
      queue.enqueue(patch(1));
      queue.enqueue(patch(2));
      const result = await queue.replay();
      expect(result.sent).toBe(0);
      expect(result.kept).toBe(2);
      expect(queue.entries().map((e) => e.url)).toEqual(["/api/v1/grocery-items/1", "/api/v1/grocery-items/2"]);
      expect(sent.length).toBe(failure === "offline" ? 0 : 1);
    }
  });

  it("runs one replay at a time", async () => {
    let calls = 0;
    const send: Sender = async () => {
      calls += 1;
      await new Promise((r) => setTimeout(r, 5));
      return { status: 200 };
    };
    const queue = new OfflineQueue(new MemoryStorage(), send);
    queue.enqueue(patch(1));
    const [a, b] = await Promise.all([queue.replay(), queue.replay()]);
    expect(a).toBe(b);
    expect(calls).toBe(1);
  });

  it("tells subscribers when the queue changes", () => {
    const queue = new OfflineQueue(new MemoryStorage(), recorder([]).send);
    let heard = 0;
    const stop = queue.subscribe(() => {
      heard += 1;
    });
    queue.enqueue(patch(1));
    stop();
    queue.enqueue(patch(2));
    expect(heard).toBe(1);
  });
});
