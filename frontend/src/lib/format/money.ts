// Money is integer cents everywhere. The app only formats cents for display and reads a typed dollar amount
// back into cents, both by string operations (no floating-point arithmetic).

/** 4550 -> "$45.50", 123456 -> "$1,234.56", -5 -> "-$0.05". */
export function formatCents(cents: number): string {
  if (!Number.isInteger(cents)) throw new Error(`cents must be an integer, got ${cents}`);
  const negative = cents < 0;
  const digits = String(Math.abs(cents)).padStart(3, "0");
  const whole = digits.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}$${whole}.${digits.slice(-2)}`;
}

/** "45", "45.5", "$45.50", "1,234.5" -> cents; "" -> null; anything else (more than 2 decimals, letters, a
 * minus sign) -> undefined, meaning "not a valid amount". */
export function parseDollarsToCents(input: string): number | null | undefined {
  const text = input.trim().replace(/^\$/, "").replace(/,/g, "");
  if (text === "") return null;
  const match = /^(\d{0,7})(?:\.(\d{0,2}))?$/.exec(text);
  if (!match || (match[1] === "" && (match[2] ?? "") === "")) return undefined;
  const whole = match[1] || "0";
  const fraction = (match[2] ?? "").padEnd(2, "0");
  return Number.parseInt(`${whole}${fraction}`, 10);
}

/** Cents -> the plain "45.50" an input field shows. */
export function centsToInput(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return "";
  return formatCents(cents).replace(/^-?\$/, "").replace(/,/g, "");
}
