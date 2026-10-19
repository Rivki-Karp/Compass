/**
 * The one number formatter (brief §3.6). It only formats: every amount comes from the API
 * already computed and rounded, so a non-integer amount is a bug and throws instead of being
 * rounded here (the browser does no money math).
 *
 * Intl "he-IL" writes a negative number as LRM + hyphen ("‎-50"), so the sign is added here:
 * "+2,914", "−50" (U+2212 minus), "0". The result is wrapped in <bdi> by <Amount>, so it reads
 * correctly inside right-to-left text.
 */

import type { Unit } from "../api/types";

export const MINUS = "−";
export const SHEKEL = "₪";

const whole = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 });

function assertWhole(value: number): void {
  if (!Number.isInteger(value)) {
    throw new Error(`amounts from the API are whole shekels; got ${value}`);
  }
}

// A hyphen-minus directly before an amount, at the start or after a space, an opening
// parenthesis or an LRM (the model writes "(\u200E-286 ₪)"); the LRM goes too, since the <bdi>
// around the number keeps its direction. Not "CAR-10" or "ב-300": a letter before the hyphen.
const TYPED_MINUS = /(^|[\s(])\u200E?-(?=\d)/g;

/**
 * A reply's text for display only (round 4, item 3): a typed minus becomes U+2212, as every
 * amount the UI formats itself has. The number guard checks the server's original text.
 */
export function displayMinus(text: string): string {
  return text.replace(TYPED_MINUS, `$1${MINUS}`);
}

/** 11000 -> "11,000"; -50 -> "−50". */
export function formatAmount(value: number): string {
  assertWhole(value);
  const digits = whole.format(Math.abs(value));
  return value < 0 ? `${MINUS}${digits}` : digits;
}

/** A difference, always with its sign: 2914 -> "+2,914", -50 -> "−50", 0 -> "0". */
export function formatSigned(value: number): string {
  assertWhole(value);
  const digits = whole.format(Math.abs(value));
  if (value > 0) return `+${digits}`;
  if (value < 0) return `${MINUS}${digits}`;
  return digits;
}

/** How a screen reader says a difference: "פלוס 2,914 שקלים", "מינוס 50 שקלים". */
export function spokenSigned(value: number): string {
  assertWhole(value);
  const digits = whole.format(Math.abs(value));
  if (value > 0) return `פלוס ${digits} שקלים`;
  if (value < 0) return `מינוס ${digits} שקלים`;
  return "אפס שקלים";
}

/**
 * An input value from the view, by unit, for a <bdi>. Non-money values arrive as exact decimal
 * strings ("6.5", "2.75"); they are parsed for display only. Money is the number alone: the
 * shekel sign goes outside the <bdi> (see <Amount>), or it would read "₪ 18,500" in RTL.
 */
export function formatInput(value: number | string | null, unit: Unit): string {
  if (value === null) return "—";
  switch (unit) {
    case "ils":
      return formatAmount(Number(value));
    case "percent":
      return `${decimal.format(Number(value))}%`;
    case "points":
    case "count":
      return decimal.format(Number(value));
    case "text":
      return String(value);
  }
}
