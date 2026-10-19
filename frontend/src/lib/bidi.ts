/**
 * Splitting free text into the runs that need their own direction (round 3, item 1).
 *
 * A Latin token: car names and codes such as "MG4", "ATTO 3", "CAR-10", "EV3", "KONA EV". It is
 * one left-to-right unit, digits included: isolating the "4" of "MG4" on its own made it read
 * "4MG" in a right-to-left paragraph. Words join on a single space, hyphen or dot; after a space
 * only a word with a Latin letter, a model number of one or two digits ("ATTO 3") or a year
 * ("COROLLA CROSS 2025") joins, so an amount after a car name stays an amount ("MG4 300 ₪").
 * A Hebrew prefix is never part of it ("ב-ATTO 3": the token is "ATTO 3").
 *
 * A number: an amount or a percentage, with its sign only at the start or after a space or
 * bracket, like the number guard reads it ("ב-300": the hyphen is a Hebrew prefix, not a minus).
 */

const WORD = String.raw`[A-Za-z0-9]*[A-Za-z][A-Za-z0-9]*`;
const NEXT = String.raw`(?:[-.][A-Za-z0-9]+|[ ](?:${WORD}|(?:\d{1,2}|(?:19|20)\d{2})(?![\d,.%]|\s*₪)))`;
const LATIN = String.raw`(?<![A-Za-z0-9])${WORD}${NEXT}*`;
const NUMBER = String.raw`(?:(?<=^|[\s([])[+\-−])?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?`;
const RUN = new RegExp(`(${LATIN})|(${NUMBER})`, "g");

export type BidiPart = string | { latin: string } | { number: string };

export function splitBidi(text: string): BidiPart[] {
  const parts: BidiPart[] = [];
  let last = 0;
  for (const match of text.matchAll(RUN)) {
    const start = match.index;
    if (start > last) parts.push(text.slice(last, start));
    parts.push(match[1] !== undefined ? { latin: match[1] } : { number: match[0] });
    last = start + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
