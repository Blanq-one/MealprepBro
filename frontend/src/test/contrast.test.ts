// AC 2b.2.2: text meets WCAG AA contrast (4.5:1) in both themes. Reads the tokens from globals.css, so a color
// change that breaks a pair fails here.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no ${selector} block`);
  const body = css.slice(start, css.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\b/g)].map((m) => [m[1] as string, (m[2] as string).toLowerCase()]));
}

const light = block(":root");
const dark = { ...light, ...block(':root[data-theme="dark"]') };

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r as number) + 0.7152 * lin(g as number) + 0.0722 * lin(b as number);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

// [text token, background token]: every pair the screens use for text
const PAIRS: [string, string][] = [
  ...["bg", "surface", "surface-2", "accent-soft"].map((bg): [string, string] => ["text", bg]),
  ...["bg", "surface", "surface-2", "accent-soft"].map((bg): [string, string] => ["muted", bg]),
  ...["bg", "surface", "surface-2", "accent-soft"].map((bg): [string, string] => ["accent-ink", bg]),
  ["accent-text", "accent"], // primary buttons, selected tiles and segments
  ["accent", "accent-text"], // the check / order badge on a selected tile
  ...["bg", "surface", "surface-2", "herb-soft"].map((bg): [string, string] => ["herb-ink", bg]),
  ...["warn-soft", "bg", "surface"].map((bg): [string, string] => ["warn", bg]),
  ...["danger-soft", "bg", "surface"].map((bg): [string, string] => ["danger", bg]),
  ["safety", "safety-soft"],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme", (_name, tokens) => {
  it.each(PAIRS)("%s on %s meets AA (4.5:1)", (fg, bg) => {
    const a = tokens[fg];
    const b = tokens[bg];
    expect(a, `--${fg}`).toBeDefined();
    expect(b, `--${bg}`).toBeDefined();
    expect(contrast(a as string, b as string)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("tokens", () => {
  it("dark mode redefines every color it needs (FLOW_SPEC §4.2)", () => {
    expect(light.bg).toBe("#fff8f1");
    expect(light.accent).toBe("#b5482f");
    const own = block(':root[data-theme="dark"]');
    for (const token of ["bg", "surface", "surface-2", "text", "muted", "border", "accent", "accent-text", "accent-soft", "herb", "honey"]) {
      expect(own[token], `--${token} in dark mode`).toBeDefined();
    }
  });
});
