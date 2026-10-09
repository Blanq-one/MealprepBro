import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, describeError, problemFrom } from "./client";

function problem(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/problem+json", ...headers },
  });
}

describe("problem+json mapping", () => {
  it("keeps the title, detail and diagnostics", async () => {
    const error = await problemFrom(
      problem(422, {
        type: "about:blank",
        title: "No plan fits this week",
        status: 422,
        detail: "drink has no recipes",
        diagnostics: [{ code: "NO_CANDIDATES_FOR_SLOT", message: "No drink recipes", slot: "drink" }],
      }),
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(422);
    expect(error.title).toBe("No plan fits this week");
    expect(error.detail).toBe("drink has no recipes");
    expect(error.diagnostics).toEqual([{ code: "NO_CANDIDATES_FOR_SLOT", message: "No drink recipes", slot: "drink" }]);
  });

  it("turns FastAPI validation errors into readable diagnostics", async () => {
    const error = await problemFrom(
      problem(422, {
        title: "Invalid request",
        detail: "The request did not pass validation.",
        errors: [{ loc: ["body", "budget_cents"], msg: "Input should be greater than or equal to 0" }],
      }),
    );
    expect(error.diagnostics).toEqual([{ message: "budget_cents: Input should be greater than or equal to 0" }]);
  });

  it("reads Retry-After for rate limits", async () => {
    const error = await problemFrom(problem(429, { title: "Too many tries", detail: "wait" }, { "retry-after": "540" }));
    expect(error.retryAfterS).toBe(540);
  });

  it("copes with a body that isn't JSON", async () => {
    const error = await problemFrom(new Response("Bad gateway", { status: 502, statusText: "Bad Gateway" }));
    expect(error.status).toBe(502);
    expect(error.title).toBe("Bad Gateway");
    expect(error.detail).toBe("Bad gateway");
  });

  it("describes errors for people", () => {
    expect(describeError(new ApiError(404, "Not found", "plan 9 not found"))).toBe("Not found: plan 9 not found");
    expect(describeError(new TypeError("Failed to fetch"))).toMatch(/offline/);
  });
});

describe("api()", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends JSON same-origin and parses the reply", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: 1 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await api<{ ok: number }>("/api/v1/x", { method: "POST", json: { a: 1 } })).toEqual({ ok: 1 });
    const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(init.credentials).toBe("same-origin");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.body).toBe('{"a":1}');
  });

  it("returns nothing for 204 and throws ApiError on a problem", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    expect(await api("/api/v1/auth/logout", { method: "POST" })).toBeUndefined();
    vi.stubGlobal("fetch", vi.fn(async () => problem(409, { title: "Conflict", detail: "already cooked" })));
    await expect(api("/api/v1/cook-batches/1/cooked", { method: "POST", json: {} })).rejects.toMatchObject({
      status: 409,
      detail: "already cooked",
    });
  });
});
