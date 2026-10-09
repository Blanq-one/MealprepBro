import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ParseResult } from "@/lib/api/types";

import { NLQuickAdd } from "./NLQuickAdd";

const parsed: ParseResult = {
  run_id: 3,
  llm_call_count: 1,
  items: [
    {
      text: "2 lb chicken thighs",
      name_as_written: "chicken thighs",
      status: "ok",
      message: null,
      ingredient_id: 1,
      ingredient_name: "chicken thigh, boneless skinless",
      quantity: "907.185",
      unit: "g",
      display: "907 g (2.00 lb)",
      location: "fridge",
      product_id: null,
      suggestions: [],
    },
    {
      text: "some rice",
      name_as_written: "rice",
      status: "needs_confirmation",
      message: "How much? The note doesn't say.",
      ingredient_id: 6,
      ingredient_name: "white rice, long grain",
      quantity: null,
      unit: null,
      display: null,
      location: "pantry",
      product_id: null,
      suggestions: [],
    },
    {
      text: "ground beef",
      name_as_written: "ground beef",
      status: "excluded",
      message: "ground beef is excluded (tagged beef (always excluded)).",
      ingredient_id: 9,
      ingredient_name: "ground beef",
      quantity: "454",
      unit: "g",
      display: "454 g",
      location: "fridge",
      product_id: null,
      suggestions: [],
    },
  ],
};

function mockFetch() {
  const calls: { url: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, body: init.body ? JSON.parse(init.body as string) : undefined });
      const reply = url.endsWith("/parse") ? parsed : [{ id: 1, name: "chicken thigh, boneless skinless" }];
      return new Response(JSON.stringify(reply), { status: url.endsWith("/bulk") ? 201 : 200 });
    }),
  );
  return calls;
}

describe("NLQuickAdd", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("saves nothing until you confirm, and then only what you chose", async () => {
    const calls = mockFetch();
    const onAdded = vi.fn();
    render(<NLQuickAdd onAdded={onAdded} />);
    await userEvent.type(screen.getByLabelText("What you have"), "2 lb chicken thighs, some rice and ground beef");
    await userEvent.click(screen.getByRole("button", { name: "Read it" }));

    expect(await screen.findByText("chicken thigh, boneless skinless")).toBeInTheDocument();
    expect(calls.map((c) => c.url)).toEqual(["/api/v1/inventory/parse"]); // parsed, nothing saved
    expect(screen.getByRole("checkbox", { name: "Add chicken thigh, boneless skinless" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Add white rice, long grain" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Add ground beef" })).toBeDisabled();
    expect(screen.getByText(/ground beef is excluded/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Add 1 item" }));
    expect(calls.map((c) => c.url)).toEqual(["/api/v1/inventory/parse", "/api/v1/inventory/bulk"]);
    expect(calls[1]?.body).toEqual({
      source: "parse",
      items: [
        { ingredient_id: 1, quantity: "907.185", unit: "g", location: "fridge", product_id: null, expiry_is_estimate: true },
      ],
    });
    expect(onAdded).toHaveBeenCalled();
  });

  it("a needs-confirmation item is added only after you give its amount and tick it", async () => {
    const calls = mockFetch();
    render(<NLQuickAdd onAdded={() => undefined} />);
    await userEvent.type(screen.getByLabelText("What you have"), "some rice");
    await userEvent.click(screen.getByRole("button", { name: "Read it" }));
    await screen.findByText("white rice, long grain");
    // untick the chicken, confirm the rice with an amount
    await userEvent.click(screen.getByRole("checkbox", { name: "Add chicken thigh, boneless skinless" }));
    const amounts = screen.getAllByRole("textbox", { name: "Amount" });
    await userEvent.type(amounts[1] as HTMLElement, "2");
    await userEvent.selectOptions(screen.getAllByRole("combobox", { name: "Unit" })[1] as HTMLElement, "lb");
    expect(screen.getByRole("button", { name: "Add 0 items" })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Add white rice, long grain" }));
    await userEvent.click(screen.getByRole("button", { name: "Add 1 item" }));
    expect(calls[1]?.body).toEqual({
      source: "parse",
      items: [{ ingredient_id: 6, quantity: "2", unit: "lb", location: "pantry", product_id: null, expiry_is_estimate: true }],
    });
  });
});
