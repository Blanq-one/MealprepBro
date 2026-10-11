import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DietReview } from "@/lib/api/types";
import { pepperoniOptions } from "@/test/fixtures";

import { HeldItemsControl } from "./Controls";

function pepperoni(usual: string | null): DietReview {
  const versions = pepperoniOptions().versions;
  return { ingredient_id: 70, slug: "pepperoni", name: "pepperoni", note: "may contain beef", decision: "held", versions: versions ? { ...versions, usual } : null };
}

describe("Settings: held items with versions (J4, M3)", () => {
  it("shows the same version choices; your usual one is saved through onUsual and never allows the item", async () => {
    const onDecide = vi.fn();
    const onUsual = vi.fn();
    render(<HeldItemsControl items={[pepperoni(null)]} onDecide={onDecide} onUsual={onUsual} />);
    await userEvent.click(screen.getByText("Comes in versions"));
    expect(screen.getByText("Check the label: the ingredients list says which meats it has.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pork \+ beef/ })).toHaveTextContent("Off your list");
    await userEvent.click(screen.getByRole("button", { name: /Turkey/ }));
    expect(onUsual).toHaveBeenLastCalledWith(expect.objectContaining({ slug: "pepperoni" }), "turkey");
    expect(onDecide).not.toHaveBeenCalled(); // choosing a version never allows pepperoni itself
    expect(screen.getByRole("switch", { name: "pepperoni" })).toHaveAttribute("aria-checked", "false");
  });

  it("the usual version comes from the server; tapping it again forgets it; Not sure never becomes the usual", async () => {
    const onUsual = vi.fn();
    render(<HeldItemsControl items={[pepperoni("turkey")]} onDecide={() => undefined} onUsual={onUsual} />);
    expect(screen.getByText("Comes in versions: you usually buy Turkey")).toBeInTheDocument();
    await userEvent.click(screen.getByText(/Comes in versions/));
    expect(screen.getByRole("button", { name: /Turkey/ })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: /Turkey/ }));
    expect(onUsual).toHaveBeenLastCalledWith(expect.anything(), null);
    await userEvent.click(screen.getByRole("button", { name: /Not sure/ }));
    expect(onUsual).toHaveBeenLastCalledWith(expect.anything(), null);
  });

  it("without a saver (onboarding) the versions aren't offered", () => {
    render(<HeldItemsControl items={[pepperoni(null)]} onDecide={() => undefined} />);
    expect(screen.queryByText(/Comes in versions/)).not.toBeInTheDocument();
  });
});
