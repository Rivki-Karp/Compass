/** Pending -> final (brief §4.4): the timing and what a screen reader hears. */

import { spokenSigned } from "../lib/format";
import type { ComparisonState } from "../state/session";

/** How long the hero keeps its `up` border after a pending result turns final (§4.4). */
export const SETTLED_FLASH_MS = 2000;

/** What a screen reader hears when a comparison arrives. When a pending result turns final, it
 * says first what the representative confirmed. */
export function announcement(comparison: ComparisonState | null): string {
  if (!comparison) return "";
  const diff = `ההפרש עודכן: ${spokenSigned(comparison.view.display_diff)}`;
  if (!comparison.settled) return diff;
  const confirmed = comparison.view.inputs.filter((i) => i.source === "representative");
  const what = confirmed.some((i) => i.id.includes("participation"))
    ? "ההשתתפות אושרה על ידי נציג."
    : "הנתונים אושרו על ידי נציג.";
  return `${what} ${diff}`;
}
