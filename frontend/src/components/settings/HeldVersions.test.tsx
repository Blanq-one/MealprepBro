import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DietReview } from "@/lib/api/types";
import { usualVersions } from "@/lib/cook/usualVersions";
import { pepperoniOptions } from "@/test/fixtures";

import { HeldItemsControl } from "./Controls";

const pepperoni: DietReview = { ingredient_id: 70, name: "pepperoni", note: "may contain beef", decision: "held", versions: pepperoniOptions().versions };

describe("Settings: held items with versions (J4)", () => {
  it("shows the same version choices; your usual one only pre-selects, the item stays held", async () => {
    const onDecide = vi.fn();
    render(<HeldItemsControl items={[pepperoni]} onDecide={onDecide} />);
    await userEvent.click(screen.getByText("Comes in versions"));
    expect(screen.getByText("Check the label: the ingredients list says which meats it has.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pork \+ beef/ })).toHaveTextContent("Off your list");
    await userEvent.click(screen.getByRole("button", { name: /Turkey/ }));
    expect(usualVersions()).toEqual({ "70": "turkey" });
    expect(screen.getByText("Comes in versions: you usually buy Turkey")).toBeInTheDocument();
    expect(onDecide).not.toHaveBeenCalled(); // choosing a version never allows pepperoni itself
    expect(screen.getByRole("switch", { name: "pepperoni" })).toHaveAttribute("aria-checked", "false");
    await userEvent.click(screen.getByRole("button", { name: /Turkey/ }));
    expect(usualVersions()).toEqual({});
  });
});
