import { describe, expect, it } from "vitest";

import { centsToInput, formatCents, parseDollarsToCents } from "./money";

describe("formatCents", () => {
  it.each([
    [0, "$0.00"],
    [5, "$0.05"],
    [99, "$0.99"],
    [4550, "$45.50"],
    [123456, "$1,234.56"],
    [100000000, "$1,000,000.00"],
    [-5, "-$0.05"],
  ])("%i -> %s", (cents, text) => {
    expect(formatCents(cents)).toBe(text);
  });

  it("refuses fractional cents", () => {
    expect(() => formatCents(1.5)).toThrow();
  });
});

describe("parseDollarsToCents (string operations, no float math)", () => {
  it.each([
    ["45", 4500],
    ["45.5", 4550],
    ["45.50", 4550],
    ["$45.50", 4550],
    [" 1,234.5 ", 123450],
    ["0.07", 7],
    [".5", 50],
    ["19.99", 1999],
    ["0.29", 29], // 0.29 * 100 would be 28.999… with floats
  ])("%s -> %i", (text, cents) => {
    expect(parseDollarsToCents(text)).toBe(cents);
  });

  it("returns null for an empty field and undefined for anything that isn't an amount", () => {
    expect(parseDollarsToCents("")).toBeNull();
    expect(parseDollarsToCents("   ")).toBeNull();
    expect(parseDollarsToCents("$")).toBeNull(); // just the sign: still empty
    for (const bad of ["4.555", "abc", "-5", "1.2.3", "."]) {
      expect(parseDollarsToCents(bad)).toBeUndefined();
    }
  });

  it("round-trips through the input format", () => {
    expect(centsToInput(4550)).toBe("45.50");
    expect(centsToInput(123456)).toBe("1234.56");
    expect(centsToInput(null)).toBe("");
    expect(parseDollarsToCents(centsToInput(1999))).toBe(1999);
  });
});
