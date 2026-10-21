/**
 * The sources of a reply's numbers, matched to the text the UI actually draws.
 *
 * The server's offsets are into the reply as it sent it. The UI draws displayMinus(text) (a
 * typed minus becomes U+2212, and the LRM the model puts before it is dropped, which moves the
 * offsets after it), and drops list markers and "**". `placeSources` moves the offsets into the
 * drawn text and keeps only the sources whose slice really is that number: a slice that does not
 * parse back to the source's value is dropped, so a drifted offset can never put a source on the
 * wrong digits. Plain text is the safe answer.
 */

import type { NumberSource } from "../api/types";

export type PlacedSource = NumberSource;

const TYPED_MINUS = /(^|[\s(])‎?-(?=\d)/g; // the same pattern as format.displayMinus
const SHOWN_NUMBER = /^[+\-−]?\d[\d,]*(?:\.\d+)?\s?%?$/;

/** Offsets of the characters displayMinus removes (the LRM before a typed minus). */
function removedAt(original: string): number[] {
  const removed: number[] = [];
  for (const match of original.matchAll(TYPED_MINUS)) {
    const lead = match[1] ?? "";
    if (match[0].length === lead.length + 2) removed.push(match.index + lead.length);
  }
  return removed;
}

function numberOf(shown: string): number {
  return Number(shown.replace(/[,%\s]/g, "").replace("−", "-"));
}

/** `sources` moved from the reply's own offsets into `shownText` (= displayMinus(original)),
 * those whose slice is the number they say. No "\r" in the reply, or nothing is kept. */
export function placeSources(
  original: string,
  shownText: string,
  sources: readonly NumberSource[] | undefined,
): PlacedSource[] {
  if (!sources?.length || original.includes("\r")) return [];
  const removed = removedAt(original);
  const moved = (offset: number) => offset - removed.filter((r) => r < offset).length;
  const placed: PlacedSource[] = [];
  for (const source of sources) {
    const start = moved(source.start);
    const end = moved(source.end);
    const shown = shownText.slice(start, end);
    if (!SHOWN_NUMBER.test(shown)) continue;
    if (numberOf(shown) !== Number(source.value)) continue;
    placed.push({ ...source, start, end });
  }
  return placed;
}

/** The sources inside [from, to), for one piece of the drawn text. */
export function within(sources: readonly PlacedSource[], from: number, to: number): PlacedSource[] {
  return sources.filter((s) => s.start >= from && s.end <= to);
}

/** "{time}" in a label, in the viewer's own time zone; without a time the clause goes. */
export function originText(label: string, at: string | null): string {
  if (!label.includes("{time}")) return label;
  const when = at ? new Date(at) : null;
  if (when && !Number.isNaN(when.getTime())) {
    const time = when.toLocaleTimeString("he-IL", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
    return label.replace("{time}", time);
  }
  return label.replace(/,?\s*[^,]*\{time\}/, "");
}
