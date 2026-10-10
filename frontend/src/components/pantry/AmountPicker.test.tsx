import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/api";
import { quickPick } from "@/test/fixtures";

import { AmountPicker } from "./AmountPicker";

function bulkApi() {
  return mockApi((call) =>
    call.path === "/api/v1/inventory/bulk" ? { status: 201, body: [{ id: 5, name: "chicken thigh, boneless skinless", display: "454 g" }] } : undefined,
  );
}

describe("the amount picker (P1)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("defaults to Full and sends the option key you pick, never a computed amount", async () => {
    const calls = bulkApi();
    const onAdded = vi.fn();
    render(<AmountPicker pick={quickPick()} online onClose={() => undefined} onAdded={onAdded} />);
    expect(screen.getByRole("dialog", { name: "chicken thigh, boneless skinless: how much?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Full/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Full · 2 lb (907 g)")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /½/ }));
    expect(screen.getByText("½ · 1 lb (454 g)")).toBeInTheDocument(); // the API's display string
    await userEvent.click(screen.getByRole("button", { name: /Freezer/ }));
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(onAdded).toHaveBeenCalled());
    expect(calls).toHaveLength(1);
    expect(calls[0]?.body).toEqual({
      source: "quick_add",
      items: [{ ingredient_id: 1, product_id: 12, location: "freezer", expiry_is_estimate: true, amount_option: "half" }],
    });
  });

  it("a custom amount goes to the server in your unit; a new unit starts from the server's value", async () => {
    const calls = bulkApi();
    render(<AmountPicker pick={quickPick()} online onClose={() => undefined} onAdded={() => undefined} />);
    await userEvent.click(screen.getByRole("button", { name: /Custom/ }));
    expect(screen.getByRole("button", { name: /Custom amount: 2/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "More custom amount" }));
    expect(screen.getByRole("button", { name: /Custom amount: 2.25/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^oz$/ }));
    expect(screen.getByRole("button", { name: /Custom amount: 32/ })).toBeInTheDocument(); // no conversion on the phone
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]?.body).toEqual({
      source: "quick_add",
      items: [{ ingredient_id: 1, product_id: null, location: "fridge", expiry_is_estimate: true, custom_amount: "32", custom_unit: "oz" }],
    });
  });

  it("an error keeps the sheet open with the message; offline, Add is off", async () => {
    mockApi(() => ({ status: 422, body: { title: "Can't add that", detail: "beef is excluded" } }));
    const { rerender } = render(<AmountPicker pick={quickPick()} online onClose={() => undefined} onAdded={() => undefined} />);
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Can't add that: beef is excluded");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    rerender(<AmountPicker pick={quickPick()} online={false} onClose={() => undefined} onAdded={() => undefined} />);
    expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
    expect(screen.getByText("Needs a connection")).toBeInTheDocument();
  });
});
