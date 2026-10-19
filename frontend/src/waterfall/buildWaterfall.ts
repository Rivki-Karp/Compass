/**
 * The waterfall's series (brief §4.3): the difference only, from zero. One floating step per
 * breakdown line in API order, then the total from 0 to `display_diff`.
 *
 * The browser does no money math. The only arithmetic here is bar positioning (running sums
 * for where each step starts and ends; never shown as a number), checked against the API's
 * totals before anything is drawn (brief §7, invariants 2 and 3). A payload that fails either
 * check throws WaterfallInvariantError, and the chart shows an error state instead of a
 * silently wrong picture.
 *
 * Provenance is resolved here too: each line names its inputs by id into `view.inputs` (value
 * and source come from there) and carries its rules with the API's labels. No label lives in
 * the frontend.
 */

import type { ComparisonView, ViewInput, ViewLine, ViewRule } from "../api/types";

export interface WaterfallStep {
  key: ViewLine["key"];
  label: string;
  value: number; // the API's net_effect
  start: number; // positioning only
  end: number; // positioning only
  inputs: ViewInput[];
  rules: ViewRule[];
}

export interface Waterfall {
  steps: WaterfallStep[];
  total: number; // the API's display_diff
  /** [min(0, lowest running sum), max(0, highest running sum)]; always contains 0. */
  domain: [number, number];
  /** The step with the largest absolute value (the first on a tie); null without steps. */
  defaultKey: WaterfallStep["key"] | null;
}

export class WaterfallInvariantError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WaterfallInvariantError";
  }
}

export function buildWaterfall(view: ComparisonView): Waterfall {
  const byId = new Map(view.inputs.map((input) => [input.id, input]));

  let running = 0;
  let low = 0;
  let high = 0;
  const steps: WaterfallStep[] = view.breakdown.map((line) => {
    if (!Number.isInteger(line.net_effect)) {
      throw new WaterfallInvariantError(`${line.key}: net_effect ${line.net_effect} is not whole`);
    }
    const start = running;
    running += line.net_effect;
    low = Math.min(low, running);
    high = Math.max(high, running);
    return {
      key: line.key,
      label: line.label,
      value: line.net_effect,
      start,
      end: running,
      inputs: line.inputs.flatMap((id) => byId.get(id) ?? []),
      rules: line.rules,
    };
  });

  // Invariant 2: the lines add up to the difference the hero shows.
  if (running !== view.display_diff) {
    throw new WaterfallInvariantError(
      `breakdown sums to ${running}, display_diff is ${view.display_diff}`,
    );
  }
  // Invariant 3: today + difference = the alternative (rounded nets; skipped when partial).
  if (
    view.today_net !== null &&
    view.alternative_net !== null &&
    view.today_net + view.display_diff !== view.alternative_net
  ) {
    throw new WaterfallInvariantError(
      `today ${view.today_net} + diff ${view.display_diff} != alternative ${view.alternative_net}`,
    );
  }

  let defaultKey: WaterfallStep["key"] | null = null;
  let largest = -1;
  for (const step of steps) {
    if (Math.abs(step.value) > largest) {
      largest = Math.abs(step.value);
      defaultKey = step.key;
    }
  }

  return { steps, total: view.display_diff, domain: [low, high], defaultKey };
}
