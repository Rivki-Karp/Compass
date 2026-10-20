/**
 * The options on screen (round 2, item 4): every alternative the server put on screen
 * (comparison_set_ready, from list_options) plus the one the agent compared last, each with its
 * latest comparison. Pure: the employee screen picks which one the hero and the panels show.
 */

import { useMemo, useState } from "react";
import { alternativeKey, type ComparisonState, type SessionState } from "../state/session";

export interface OptionItem {
  key: string;
  comparison: ComparisonState;
}

/** Every option, best first (by the signed difference); ties keep their order. */
export function optionList(state: Pick<SessionState, "optionKeys" | "comparisons" | "comparison">) {
  const keys = [...state.optionKeys];
  if (state.comparison) {
    const latest = alternativeKey(state.comparison.view);
    if (!keys.includes(latest)) keys.push(latest);
  }
  return keys
    .map((key) => ({ key, comparison: state.comparisons[key] }))
    .filter((o): o is OptionItem => o.comparison !== undefined)
    .sort((a, b) => rank(b.comparison) - rank(a.comparison));
}

/** An option's place: its difference, or its own net while today's car is unknown (the same
 * order, since today is common to all). */
function rank(comparison: ComparisonState): number {
  const { display_diff, alternative_net } = comparison.view;
  return display_diff ?? alternative_net ?? 0;
}

/** The option shown by default: the one the agent compared last, else the best one. */
export function defaultOptionKey(
  options: OptionItem[],
  latest: ComparisonState | null,
): string | null {
  if (latest) {
    const key = alternativeKey(latest.view);
    if (options.some((o) => o.key === key)) return key;
  }
  return options[0]?.key ?? null;
}

/** What the hero, the waterfall, the provenance strip and the inputs card show. */
export function shownComparison(
  options: OptionItem[],
  latest: ComparisonState | null,
  selected: string | null,
): ComparisonState | null {
  if (options.length < 2) return latest ?? options[0]?.comparison ?? null;
  const key =
    selected && options.some((o) => o.key === selected)
      ? selected
      : defaultOptionKey(options, latest);
  return options.find((o) => o.key === key)?.comparison ?? latest;
}

type OptionsState = Pick<SessionState, "optionKeys" | "comparisons" | "comparison">;

/** The options, the one shown, and how to pick another. A pick holds until the agent compares
 * something new (a `compare` the model called), which is then shown. */
export function useOptionSelection(state: OptionsState) {
  const options = useMemo(() => optionList(state), [state]);
  const lastAgentSeq = Math.max(
    0,
    ...Object.values(state.comparisons)
      .filter((c) => c.origin === "tool")
      .map((c) => c.seq),
  );
  const [chosen, setChosen] = useState<{ key: string; at: number } | null>(null);
  const selectedKey = chosen && chosen.at >= lastAgentSeq ? chosen.key : null;
  const comparison = shownComparison(options, state.comparison, selectedKey);
  return {
    options,
    comparison,
    selected: comparison ? alternativeKey(comparison.view) : null,
    select: (key: string) => setChosen({ key, at: lastAgentSeq }),
  };
}
