import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CorrectOptions, IngredientHit } from "@/lib/api/types";
import { mockApi } from "@/test/api";
import { lot } from "@/test/fixtures";

import { CorrectAmountSheet } from "./CorrectAmountSheet";
import { IngredientSearch } from "./IngredientSearch";

const options: CorrectOptions = {
  lot_id: 31,
  name: "cauliflower, frozen",
  display: "16 oz (454 g)",
  estimated: false,
  package_display: "your bag: 16 oz (454 g)",
  fractions: [
    { key: "three_quarters", quantity: "340.194", unit: "g", display: "¾ · 12 oz (340 g)" },
    { key: "half", quantity: "226.796", unit: "g", display: "½ · 8 oz (227 g)" },
    { key: "quarter", quantity: "113.398", unit: "g", display: "¼ · 4 oz (113 g)" },
  ],
  presets: [{ key: "12oz", label: "12 oz bag", quantity: "340.194", unit: "g", container: "bag", default: true, is_estimate: true }],
  custom_units: [{ unit: "oz", label: "oz", step: "1", start: "16" }],
};

describe("Correct amount, on any lot (M2)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("quick taps for what's left of the package, another size, or custom; the server works out the amount", async () => {
    const calls = mockApi((call) => (call.path.endsWith("/correct-options") ? { body: options } : call.method === "PATCH" ? { body: lot({ display: "8 oz" }) } : undefined));
    const onChanged = vi.fn();
    render(<CorrectAmountSheet lot={lot({ id: 31, name: "cauliflower, frozen" })} online onClose={() => undefined} onChanged={onChanged} />);
    expect(await screen.findByText("What's left of your bag: 16 oz (454 g)?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled(); // nothing picked yet
    await userEvent.click(screen.getByRole("button", { name: "½ · 8 oz (227 g)" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(calls.at(-1)).toMatchObject({ method: "PATCH", path: "/api/v1/inventory/31", body: { package_fraction: "half" } });

    await userEvent.click(screen.getByRole("button", { name: "12 oz bag" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.at(-1)?.body).toEqual({ preset: "12oz" }));

    await userEvent.click(screen.getByRole("button", { name: "Custom" }));
    expect(screen.getByRole("button", { name: /Custom amount: 16/ })).toBeInTheDocument(); // the server's start
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.at(-1)?.body).toEqual({ quantity: "16", unit: "oz" }));
  });
});

describe("close matches in search (M7)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("a name with no ingredient of its own shows its closest one, labeled", async () => {
    const hit: IngredientHit = {
      id: 9,
      name: "peas, frozen",
      slug: "peas-frozen",
      category: "vegetable",
      matched_alias: "canned peas",
      score: 0.995,
      status: "allowed",
      reasons: [],
      frequency_caps: [],
      closest_match: true,
      label: "Closest match: peas, frozen",
    };
    mockApi(() => ({ body: [hit] }));
    const onPick = vi.fn();
    render(<IngredientSearch onPick={onPick} />);
    await userEvent.type(screen.getByLabelText("Add something"), "canned peas");
    await userEvent.click(await screen.findByRole("button", { name: "Closest match: peas, frozen" }));
    expect(onPick).toHaveBeenCalledWith(hit);
  });
});
