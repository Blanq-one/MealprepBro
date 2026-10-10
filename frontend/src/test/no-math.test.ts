// Phase 2 AC 7 / 2b.2 AC 3: the frontend does no nutrition, unit or money arithmetic. Every kcal, gram,
// dollar and total arrives from the API; the app formats cents and lays things out. This audit scans every
// app source file (tests and the cents formatter aside) for arithmetic on a nutrition, amount or money value,
// and for sums (reduce).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");
const ALLOWED = new Set([
  "lib/format/money.ts", // cents -> "$45.50" and typed dollars -> cents, by string operations
  "lib/api/schema.d.ts", // generated types
]);
const SENSITIVE = /(kcal|calor|cents|price|cost|protein|carb|iron|fiber|fat\b|gram|_g$|_mg$|quantity|amount|portion|nutrient|weight|density|ounce|pound)/i;
const UNIT_NAMES = /^(g|kg|lb|lbs|oz|ml|l|tsp|tbsp|cups?|fl_oz)$/i;

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "test" ? [] : sources(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

/** The code without comments and string text (template literals keep their ${…} expressions). */
function codeOnly(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/\s\/\/ .*$/gm, "")
    .replace(/`(?:[^`\\]|\\.)*`/g, (literal) => [...literal.matchAll(/\$\{([^}]*)\}/g)].map((m) => ` ${m[1]} `).join(" "))
    .replace(/"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'/g, '""')
    .replace(/>[^<>{}]*</g, "><"); // JSX text
}

const OPERAND = String.raw`[A-Za-z_$][\w$]*(?:(?:\?\.|\.)[A-Za-z_$][\w$]*|\[[^\]]*\])*`;
// A binary operator with spaces around it, as the code is written (so regex literals like /_/g and JSX text like
// "g/day" aren't mistaken for division).
const BINARY = new RegExp(String.raw`(${OPERAND}|\))\s+([+\-*/%])(?![=+\-/*>])\s+(${OPERAND}|\d[\d_.]*|\()`, "g");

export function arithmeticOn(code: string): string[] {
  const found: string[] = [];
  for (const m of code.matchAll(BINARY)) {
    const [whole, left, , right] = m;
    const names = [left, right].map((side) => (side ?? "").split(/\?\.|\./).pop() ?? "");
    if (names.some((n) => SENSITIVE.test(n) || UNIT_NAMES.test(n))) found.push(whole.trim());
  }
  for (const m of code.matchAll(/\.reduce\s*\(/g)) found.push(m[0]);
  return found;
}

describe("no nutrition, unit or money arithmetic in the frontend", () => {
  it("the audit catches the kinds of math the app must leave to the server", () => {
    expect(arithmeticOn("const total = meal.kcal + snack.kcal;")).toHaveLength(1);
    expect(arithmeticOn("const dollars = item.price_cents / 100;")).toHaveLength(1);
    expect(arithmeticOn("const g = lb * 453.59;")).toHaveLength(1);
    expect(arithmeticOn("const grams = quantity * 453.59;")).toHaveLength(1);
    expect(arithmeticOn("const sum = days.reduce((a, d) => a + d, 0);")).toHaveLength(1);
    expect(arithmeticOn("const next = index + 1;")).toHaveLength(0);
    expect(arithmeticOn(codeOnly('const label = `${n} kcal`; const url = "/api/v1/settings/preview";'))).toHaveLength(0);
  });

  it("finds none in the app's source files", () => {
    const files = sources(SRC);
    expect(files.length).toBeGreaterThan(50); // it really scans the app
    const hits = files
      .filter((path) => !ALLOWED.has(relative(SRC, path).replace(/\\/g, "/")))
      .flatMap((path) => arithmeticOn(codeOnly(readFileSync(path, "utf8"))).map((hit) => `${relative(SRC, path)}: ${hit}`));
    expect(hits).toEqual([]);
  });
});
