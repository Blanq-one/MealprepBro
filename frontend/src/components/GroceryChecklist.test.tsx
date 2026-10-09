import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { groceryByCategory, groceryByStore } from "@/test/fixtures";

import { GroceryChecklist } from "./GroceryChecklist";

function sections() {
  return screen.getAllByRole("region").map((r) => within(r).getByRole("heading").textContent);
}

describe("GroceryChecklist", () => {
  it("groups by store, with stock-up items and staples in their own sections", () => {
    render(<GroceryChecklist list={groceryByStore} onPatch={() => undefined} />);
    expect(sections()).toEqual(["Stop & Shop", "Price Rite", "Also buy this week (stock-up)", "Check you have"]);
    const stopShop = screen.getByRole("region", { name: "Stop & Shop" });
    expect(within(stopShop).getByText("chicken thigh, boneless skinless")).toBeInTheDocument();
    expect(within(stopShop).getByText("green cabbage")).toBeInTheDocument();
    expect(within(stopShop).getByText("$15.46")).toBeInTheDocument();
    const stockUp = screen.getByRole("region", { name: "Also buy this week (stock-up)" });
    expect(within(stockUp).getByText("protein powder, double chocolate")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Price Rite" })).getByText(/flour tortilla/)).toBeInTheDocument();
  });

  it("groups by category when the server sent category groups", () => {
    render(<GroceryChecklist list={groceryByCategory} onPatch={() => undefined} />);
    expect(sections()).toEqual(["Protein", "Vegetable", "Grain", "Also buy this week (stock-up)", "Check you have"]);
    expect(within(screen.getByRole("region", { name: "Vegetable" })).getByText("green cabbage")).toBeInTheDocument();
  });

  it("checks an item off with one tap", async () => {
    const onPatch = vi.fn();
    render(<GroceryChecklist list={groceryByStore} onPatch={onPatch} />);
    await userEvent.click(screen.getByRole("checkbox", { name: "Got green cabbage" }));
    expect(onPatch).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }), { checked: true });
  });

  it("sends the actual weight and price as typed (the server converts and records them)", async () => {
    const onPatch = vi.fn();
    render(<GroceryChecklist list={groceryByStore} onPatch={onPatch} />);
    await userEvent.click(screen.getByRole("button", { name: /chicken thigh, boneless skinless/ }));
    await userEvent.type(screen.getByLabelText(/Actual weight/), "2.31");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Unit" }), "lb");
    await userEvent.type(screen.getByLabelText(/Price paid/), "12.79");
    await userEvent.click(screen.getByRole("button", { name: "Save and check off" }));
    expect(onPatch).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }), {
      checked: true,
      purchased_amount: "2.31",
      purchased_unit: "lb",
      actual_price_cents: 1279,
    });
  });

  it("shows the server's state for checked items; staples can be ticked as a reminder", () => {
    const list = structuredClone(groceryByStore);
    const first = list.groups[0]?.items[0];
    if (first) Object.assign(first, { checked: true, purchased: "1,048 g (2.31 lb)", actual_price_display: "$12.79" });
    render(<GroceryChecklist list={list} onPatch={() => undefined} />);
    expect(screen.getByRole("checkbox", { name: "Got chicken thigh, boneless skinless" })).toBeChecked();
    expect(screen.getByText("Got 1,048 g (2.31 lb) for $12.79")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Got salt" })).toBeInTheDocument();
  });
});
