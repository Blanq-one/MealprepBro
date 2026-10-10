import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/api";
import { batchDetail } from "@/test/fixtures";

import { CookingMode } from "./CookingMode";

function stubWakeLock() {
  const release = vi.fn(async () => undefined);
  const request = vi.fn(async () => ({ release }));
  Object.defineProperty(navigator, "wakeLock", { value: { request }, configurable: true });
  return { request, release };
}

describe("cooking mode", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(navigator, "wakeLock");
  });

  it("goes one step at a time, back and next, with the safety lines highlighted", async () => {
    stubWakeLock();
    render(<CookingMode batch={batchDetail()} online />);
    expect(screen.getByText("Get ready")).toBeInTheDocument();
    expect(screen.getByText("uses 6 oz, about a quarter of your pack · 1.6 lb left after")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
    expect(screen.getByText("Cut the chicken into 1-inch pieces.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Step 2 of 3")).toBeInTheDocument();
    expect(screen.getByText("425°F · 20 min")).toBeInTheDocument();
    expect(screen.getByTestId("safety-note")).toHaveTextContent("Cook chicken to 165°F (poultry).");
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
  });

  it("ends with Mark cooked", async () => {
    stubWakeLock();
    const calls = mockApi((call) => (call.path === "/api/v1/cook-batches/44/cooked" ? { body: { batch_id: 44, status: "cooked", title: "Chicken", deductions: [{ ingredient_id: 1, name: "chicken thigh", taken: "6 oz", shortfall: null }], open_packages: [] } } : undefined));
    render(<CookingMode batch={batchDetail()} online />);
    for (const name of ["Start", "Next", "Next", "Next"]) await userEvent.click(screen.getByRole("button", { name }));
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark cooked" }));
    expect(await screen.findByText("Cooked: inventory updated")).toBeInTheDocument();
    expect(calls.at(-1)).toMatchObject({ method: "POST", path: "/api/v1/cook-batches/44/cooked" });
  });

  it("keeps the screen awake while open and lets go when you leave", async () => {
    const { request, release } = stubWakeLock();
    const { unmount } = render(<CookingMode batch={batchDetail()} online />);
    await waitFor(() => expect(request).toHaveBeenCalledWith("screen"));
    expect(await screen.findByText("Screen stays on")).toBeInTheDocument();
    act(() => unmount());
    await waitFor(() => expect(release).toHaveBeenCalled());
  });

  it("offline, Mark cooked needs a connection", async () => {
    render(<CookingMode batch={batchDetail()} online={false} />);
    for (const name of ["Start", "Next", "Next", "Next"]) await userEvent.click(screen.getByRole("button", { name }));
    expect(screen.getByRole("button", { name: "Mark cooked" })).toBeDisabled();
    expect(screen.getByText("Needs a connection")).toBeInTheDocument();
  });
});
