/** Pending -> final (brief §4.4): the timing and what a screen reader hears. */

import { spokenDiff } from "../lib/format";
import type { ComparisonState } from "../state/session";

/** How long the hero keeps its `up` border after a pending result turns final (§4.4). */
export const SETTLED_FLASH_MS = 2000;

/** What a screen reader hears when a comparison arrives. When a pending result turns final, it
 * says first what the representative confirmed; a later comparison that repeats the settled
 * result gives the same text, so it isn't announced twice. */
export function announcement(comparison: ComparisonState | null): string {
  if (!comparison) return "";
  const { view } = comparison;
  const diff =
    view.display_diff === null
      ? `החישוב עודכן: ${spokenDiff(view)}`
      : `ההפרש עודכן: ${spokenDiff(view)}`;
  if (!comparison.settled) return diff;
  const confirmed = comparison.view.inputs.filter((i) => i.source === "representative");
  const what = confirmed.some((i) => i.id.includes("participation"))
    ? "ההשתתפות אושרה על ידי נציג."
    : confirmed.some((i) => i.id === "group")
      ? "הקבוצה אושרה על ידי נציג."
      : "הנתונים אושרו על ידי נציג.";
  return `${what} ${diff}`;
}
