import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/api";
import { cauliflowerOptions, lot, pepperoniOptions, turkeyPepperoniOptions } from "@/test/fixtures";

import { AddFlow } from "./AddFlow";
import { VersionSheet } from "./VersionSheet";

function api() {
  return mockApi((call) => {
    if (call.path === "/api/v1/ingredients/61/add-options") return { body: cauliflowerOptions() };
    if (call.path === "/api/v1/ingredients/70/add-options") return { body: pepperoniOptions() };
    if (call.path === "/api/v1/ingredients/73/add-options") return { body: turkeyPepperoniOptions() };
    if (call.path === "/api/v1/inventory/bulk") return { status: 201, body: [lot({ id: 90, name: "cauliflower, frozen", display: "12 oz", quantity_is_estimate: true })] };
    if (call.path === "/api/v1/inventory/31/version") return { body: lot({ id: 91, ingredient_id: 73, name: "pepperoni, turkey", display: "6 oz" }) };
    return undefined;
  });
}

describe("the add flow (J4, J5)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("form, then package size; Not sure is the default and adds the usual size as an estimate", async () => {
    const calls = api();
    const onAdded = vi.fn();
    render(<AddFlow ingredient={{ id: 61, name: "cauliflower, frozen" }} context="pantry" online onClose={() => undefined} onAdded={onAdded} />);
    expect(await screen.findByRole("dialog", { name: "Add Cauliflower" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Frozen florets/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByRole("button", { name: /oz bag/ }).map((b) => b.textContent)).toEqual(["10 oz bag", "12 oz bag", "16 oz bag"]);
    expect(screen.getByRole("button", { name: "Not sure" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("not-sure-note")).toHaveTextContent("Adds the usual size (12 oz bag), marked as an estimate");
    expect(screen.getByRole("button", { name: /Freezer/ })).toHaveAttribute("aria-pressed", "true"); // frozen lives in the freezer
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(onAdded).toHaveBeenCalled());
    expect(calls.at(-1)?.body).toEqual({
      source: "quick_add",
      items: [{ ingredient_id: 61, location: "freezer", expiry_is_estimate: true, not_sure: true }],
    });
  });

  it("a package size or the fresh form sends its own key; Custom sends your amount in a server unit", async () => {
    const calls = api();
    render(<AddFlow ingredient={{ id: 61, name: "cauliflower, frozen" }} context="pantry" online onClose={() => undefined} onAdded={() => undefined} />);
    await userEvent.click(await screen.findByRole("button", { name: "16 oz bag" }));
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(1));
    expect(calls.at(-1)?.body).toMatchObject({ items: [{ ingredient_id: 61, preset: "16oz", not_sure: false }] });

    await userEvent.click(screen.getByRole("button", { name: "Custom" }));
    await userEvent.click(screen.getByRole("button", { name: /^oz$/ }));
    expect(screen.getByRole("button", { name: /Custom amount: 12/ })).toBeInTheDocument(); // the server's start, no conversion here
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(2));
    expect(calls.at(-1)?.body).toMatchObject({ items: [{ ingredient_id: 61, quantity: "12", unit: "oz", not_sure: false }] });

    await userEvent.click(screen.getByRole("button", { name: /Fresh head/ }));
    expect(screen.getByRole("button", { name: /Fridge/ })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "medium head (about 2 lb)" }));
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(3));
    expect(calls.at(-1)?.body).toMatchObject({ items: [{ ingredient_id: 60, preset: "medium", location: "fridge" }] });
  });

  it("the version sheet: label guidance, pork + beef is refused, turkey goes on to its own sizes", async () => {
    const calls = api();
    const onAdded = vi.fn();
    render(<AddFlow ingredient={{ id: 70, name: "pepperoni" }} context="pantry" online onClose={() => undefined} onAdded={onAdded} />);
    expect(await screen.findByText("Which pepperoni is it?")).toBeInTheDocument();
    expect(screen.getByText("Check the label: the ingredients list says which meats it has.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pork only/ })).toHaveTextContent("counts toward your limit for pork");
    expect(screen.getByRole("button", { name: /Chicken/ })).toHaveTextContent("nutrition estimated");

    await userEvent.click(screen.getByRole("button", { name: /Pork \+ beef/ }));
    expect(screen.getByRole("status")).toHaveTextContent("Off your list: it contains beef, so I won't add it.");
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("choosing turkey asks again for the turkey pepperoni and adds it, never the held generic", async () => {
    const calls = api();
    const onAdded = vi.fn();
    render(<AddFlow ingredient={{ id: 70, name: "pepperoni" }} context="pantry" online onClose={() => undefined} onAdded={onAdded} />);
    await userEvent.click(await screen.findByRole("button", { name: /Turkey/ }));
    expect(await screen.findByRole("button", { name: "5 oz pack" })).toBeInTheDocument();
    expect(calls.map((c) => c.path)).toContain("/api/v1/ingredients/73/add-options");
    await userEvent.click(screen.getByRole("button", { name: "8 oz pack" }));
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(onAdded).toHaveBeenCalled());
    expect(calls.at(-1)?.body).toMatchObject({ items: [{ ingredient_id: 73, preset: "8oz" }] });
    expect(calls.some((c) => c.method !== "GET" && c.path.includes("ingredient-preferences"))).toBe(false); // nothing allowed
  });

  it("in 'What do you have?', Not sure about the version keeps it held and out of this search", async () => {
    api();
    const onExtra = vi.fn();
    render(<AddFlow ingredient={{ id: 70, name: "pepperoni" }} context="have" online onClose={() => undefined} onAdded={() => undefined} onExtra={onExtra} />);
    await userEvent.click(await screen.findByRole("button", { name: /Not sure/ }));
    expect(screen.getByRole("status")).toHaveTextContent("Pepperoni stays held until you check the label, so I won't use it this time.");
    expect(onExtra).not.toHaveBeenCalled();
  });

  it("in 'What do you have?', Have it carries the size's amount; Could buy carries none; Save to pantry adds a lot", async () => {
    const calls = api();
    const onExtra = vi.fn();
    const onAdded = vi.fn();
    render(<AddFlow ingredient={{ id: 61, name: "cauliflower, frozen" }} context="have" online onClose={() => undefined} onAdded={onAdded} onExtra={onExtra} />);
    await userEvent.click(await screen.findByRole("button", { name: "16 oz bag" }));
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(onExtra).toHaveBeenLastCalledWith({ ingredient_id: 61, name: "cauliflower, frozen", status: "have", preset: "16oz", presetLabel: "16 oz bag", quantity: "453.592", unit: "g" });

    await userEvent.click(screen.getByRole("button", { name: /Not sure/ }));
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(onExtra).toHaveBeenLastCalledWith(expect.objectContaining({ preset: "12oz", presetLabel: "12 oz bag, not sure", quantity: "340.194" }));

    await userEvent.click(screen.getByRole("button", { name: /Could buy/ }));
    expect(screen.queryByRole("group", { name: "How much" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(onExtra).toHaveBeenLastCalledWith({ ingredient_id: 61, name: "cauliflower, frozen", status: "could_buy" });

    await userEvent.click(screen.getByRole("button", { name: /Have it/ }));
    await userEvent.click(screen.getByRole("switch", { name: "Save to pantry" }));
    await userEvent.click(screen.getByRole("button", { name: "Add to pantry" }));
    await waitFor(() => expect(onAdded).toHaveBeenCalled());
    expect(calls.at(-1)?.body).toMatchObject({ items: [{ ingredient_id: 61, not_sure: true, location: "freezer" }] });
  });

  it("an excluded item says why and adds nothing", async () => {
    mockApi(() => ({ body: { ...cauliflowerOptions(), state: "excluded", message: "Beef is off your list, so I won't use it.", food: null, name: "ground beef" } }));
    render(<AddFlow ingredient={{ id: 5, name: "ground beef" }} context="have" online onClose={() => undefined} onAdded={() => undefined} onExtra={() => undefined} />);
    expect(await screen.findByRole("status")).toHaveTextContent("Beef is off your list, so I won't use it.");
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument();
  });
});

describe("the version sheet for a held lot (J4)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sets the lot to the version on its label; Not sure leaves it held", async () => {
    const calls = api();
    const onChanged = vi.fn();
    const onClose = vi.fn();
    const held = lot({ id: 31, ingredient_id: 70, name: "pepperoni", display: "6 oz", state: "held", has_versions: true });
    render(<VersionSheet lot={held} online onClose={onClose} onChanged={onChanged} />);
    await userEvent.click(await screen.findByRole("button", { name: /Turkey/ }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(expect.objectContaining({ ingredient_id: 73 })));
    expect(calls.at(-1)).toMatchObject({ method: "POST", path: "/api/v1/inventory/31/version", body: { ingredient_id: 73 } });
    await userEvent.click(screen.getByRole("button", { name: /Not sure/ }));
    expect(onClose).toHaveBeenCalled();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });
});
