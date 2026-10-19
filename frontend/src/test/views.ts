/** Comparison views for tests: the ones in the recorded demo logs, and synthetic ones. */

import type { ComparisonView, SessionEvent } from "../api/types";
import walkthroughLog from "./fixtures/walkthrough.json";

export function must<T>(value: T | null | undefined): T {
  if (value === null || value === undefined) throw new Error("missing in fixture");
  return value;
}

/** Every comparison view in a fixture log, in order. */
export function views(log: unknown): ComparisonView[] {
  return (log as SessionEvent[]).flatMap((e) =>
    e.type === "comparison_ready" ? [e.payload.view] : [],
  );
}

/** A synthetic view: the walkthrough's shape with other lines and nets. */
export function viewWith(
  lines: [ComparisonView["breakdown"][number]["key"], number][],
  diff: number,
  today = 11000,
  alternative = today + diff,
): ComparisonView {
  const base = must(views(walkthroughLog)[0]);
  return {
    ...base,
    breakdown: lines.map(([key, net_effect]) => ({
      key,
      label: `label:${key}`,
      net_effect,
      inputs: ["base_salary"],
      rules: [],
    })),
    display_diff: diff,
    today_net: today,
    alternative_net: alternative,
    direction: diff > 0 ? "up" : diff < 0 ? "down" : "flat",
  };
}
