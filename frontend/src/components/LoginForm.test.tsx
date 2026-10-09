import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "./LoginForm";

function reply(status: number, body?: unknown, headers: Record<string, string> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      body === undefined
        ? new Response(null, { status })
        : new Response(JSON.stringify(body), { status, headers: { "content-type": "application/problem+json", ...headers } }),
    ),
  );
}

async function signIn(password = "hunter22") {
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("LoginForm", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses a password field the phone can fill in", () => {
    render(<LoginForm onSignedIn={() => undefined} />);
    const field = screen.getByLabelText("Password");
    expect(field).toHaveAttribute("type", "password");
    expect(field).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
  });

  it("signs in", async () => {
    reply(204);
    const onSignedIn = vi.fn();
    render(<LoginForm onSignedIn={onSignedIn} />);
    await signIn();
    expect(onSignedIn).toHaveBeenCalled();
    const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/login");
    expect(JSON.parse(init.body as string)).toEqual({ password: "hunter22" });
  });

  it("says when the password is wrong", async () => {
    reply(401, { title: "Wrong password", status: 401, detail: "That password isn't right." });
    render(<LoginForm onSignedIn={() => undefined} />);
    await signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent("That password isn't right.");
  });

  it("says how long to wait after too many tries", async () => {
    reply(429, { title: "Too many tries", status: 429, detail: "wait" }, { "retry-after": "540" });
    render(<LoginForm onSignedIn={() => undefined} />);
    await signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many tries. Try again in 9 minutes.");
  });

  it("explains when sign-in isn't set up", async () => {
    reply(503, { title: "Sign-in isn't set up", status: 503, detail: "Set AUTH_PASSWORD_HASH and SESSION_SECRET." });
    render(<LoginForm onSignedIn={() => undefined} />);
    await signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign-in isn't set up yet. Set AUTH_PASSWORD_HASH");
  });

  it("says when the server can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    render(<LoginForm onSignedIn={() => undefined} />);
    await signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent("offline");
  });
});
