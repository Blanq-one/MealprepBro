import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryStorage, OfflineQueue, type QueuedRequest, type Sender } from "@/lib/offline/queue";
import { mockApi } from "@/test/api";

import { markUrl, sendMark } from "./marks";

describe("♥ and 🔖 marks", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("online, a mark is sent at once (PUT on, DELETE off)", async () => {
    const calls = mockApi(() => ({ status: 204 }));
    const queue = new OfflineQueue(new MemoryStorage());
    expect(await sendMark(11, "favorite", true, "Curry", { online: true, queue })).toBe("sent");
    expect(await sendMark(11, "saved", false, "Curry", { online: true, queue })).toBe("sent");
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(["PUT /api/v1/recipes/11/favorite", "DELETE /api/v1/recipes/11/saved"]);
    expect(queue.entries()).toEqual([]);
  });

  it("offline, it is queued and replayed once when you're back", async () => {
    const sent: QueuedRequest[] = [];
    const send: Sender = async (entry) => {
      sent.push(entry);
      return { status: 204 };
    };
    const queue = new OfflineQueue(new MemoryStorage(), send);
    expect(await sendMark(11, "favorite", true, "Curry", { online: false, queue })).toBe("queued");
    expect(queue.entries()).toMatchObject([{ method: "PUT", url: markUrl(11, "favorite"), label: "favorite Curry" }]);
    await queue.replay();
    await queue.replay(); // a second replay sends nothing more
    expect(sent.map((e) => `${e.method} ${e.url}`)).toEqual(["PUT /api/v1/recipes/11/favorite"]);
    expect(queue.entries()).toEqual([]);
  });

  it("a dropped connection queues it; a refusal is an error the screen reverts", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    const queue = new OfflineQueue(new MemoryStorage());
    expect(await sendMark(11, "saved", true, "Curry", { online: true, queue })).toBe("queued");
    mockApi(() => ({ status: 404, body: { title: "Not found", detail: "recipe 11 not found" } }));
    await expect(sendMark(11, "saved", true, "Curry", { online: true, queue })).rejects.toThrow("the server said no (404)");
  });
});
