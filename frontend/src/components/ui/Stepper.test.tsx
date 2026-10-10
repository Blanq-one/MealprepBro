import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Stepper, stepValue } from "./Stepper";

function Harness({ start, min = 800, max = 6000, step = 50, onValue }: { start: number | null; min?: number; max?: number; step?: number; onValue?: (v: number) => void }) {
  const [value, setValue] = useState<number | null>(start);
  return (
    <Stepper
      label="Calories a day"
      unit="kcal"
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={(v) => {
        setValue(v);
        onValue?.(v);
      }}
    />
  );
}

const shown = () => screen.getByRole("status").textContent;

describe("Stepper", () => {
  afterEach(() => vi.useRealTimers());

  it("steps by its increment and stays inside its bounds", async () => {
    render(<Harness start={5950} />);
    const more = screen.getByRole("button", { name: "More calories a day" });
    await userEvent.click(more);
    expect(shown()).toBe("6,000");
    expect(more).toBeDisabled(); // at the top bound
    await userEvent.click(screen.getByRole("button", { name: "Less calories a day" }));
    expect(shown()).toBe("5,950");
  });

  it("can't go below its minimum", async () => {
    render(<Harness start={850} />);
    const less = screen.getByRole("button", { name: "Less calories a day" });
    await userEvent.click(less);
    expect(shown()).toBe("800");
    expect(less).toBeDisabled();
  });

  it("press and hold repeats until the finger lifts, and the lift doesn't add one more", () => {
    vi.useFakeTimers();
    const values: number[] = [];
    render(<Harness start={1800} onValue={(v) => values.push(v)} />);
    const more = screen.getByRole("button", { name: "More calories a day" });
    fireEvent.pointerDown(more, { button: 0 });
    act(() => {
      vi.advanceTimersByTime(399);
    });
    expect(values).toEqual([]); // a tap, so far
    act(() => {
      vi.advanceTimersByTime(1 + 90 * 4);
    });
    fireEvent.pointerUp(more);
    fireEvent.click(more); // the click that ends a long press
    expect(values).toEqual([1850, 1900, 1950, 2000, 2050]);
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(values).toHaveLength(5); // stopped
    fireEvent.pointerDown(more, { button: 0 });
    fireEvent.pointerUp(more);
    fireEvent.click(more); // a plain tap steps once
    expect(values.at(-1)).toBe(2100);
  });

  it("holding stops at the bound", () => {
    vi.useFakeTimers();
    const values: number[] = [];
    render(<Harness start={5900} onValue={(v) => values.push(v)} />);
    fireEvent.pointerDown(screen.getByRole("button", { name: "More calories a day" }), { button: 0 });
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(values).toEqual([5950, 6000]);
  });

  it("a tap on the value types it; out of range shows the reason", async () => {
    render(<Harness start={1800} />);
    await userEvent.click(screen.getByRole("button", { name: /Calories a day: 1,800 kcal/ }));
    const input = screen.getByRole("textbox", { name: "Calories a day, type a number" });
    expect(input).toHaveAttribute("inputmode", "numeric");
    await userEvent.clear(input);
    await userEvent.type(input, "9000{Enter}");
    expect(shown()).toBe("9,000");
    expect(screen.getByRole("alert")).toHaveTextContent("Calories a day: pick from 800 to 6,000 kcal.");
  });

  it("an empty value starts at the minimum on +", async () => {
    render(<Harness start={null} min={25} max={3000} step={25} />);
    expect(shown()).toBe("—");
    expect(screen.getByRole("button", { name: "Less calories a day" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "More calories a day" }));
    expect(shown()).toBe("25");
  });

  it("decimal steps don't drift", () => {
    expect(stepValue(0.2, 1, { min: 0.1, max: 10, step: 0.1 })).toBe(0.3);
    expect(stepValue(1.75, 1, { min: 0.25, max: 10, step: 0.25 })).toBe(2);
    expect(stepValue(0.25, -1, { min: 0.25, max: 10, step: 0.25 })).toBe(0.25);
  });
});
