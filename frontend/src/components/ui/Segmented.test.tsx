import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Segmented } from "./Segmented";

function Harness() {
  const [value, setValue] = useState<"store" | "category">("store");
  return (
    <Segmented
      label="Group by"
      options={[
        { value: "store", label: "By store" },
        { value: "category", label: "By category" },
      ]}
      value={value}
      onChange={setValue}
    />
  );
}

describe("Segmented (fixed selected state)", () => {
  it("marks exactly the chosen segment with aria-pressed and a check", async () => {
    render(<Harness />);
    const store = screen.getByRole("button", { name: /By store/ });
    const category = screen.getByRole("button", { name: /By category/ });
    expect(store).toHaveAttribute("aria-pressed", "true");
    expect(category).toHaveAttribute("aria-pressed", "false");
    expect(store).toHaveTextContent("✓");
    expect(category).not.toHaveTextContent("✓");

    await userEvent.click(category);
    expect(store).toHaveAttribute("aria-pressed", "false");
    expect(category).toHaveAttribute("aria-pressed", "true");
    expect(category).toHaveTextContent("✓");
    expect(screen.getByRole("group", { name: "Group by" })).toBeInTheDocument();
  });
});
