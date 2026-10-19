/**
 * Which run the engine room shows. A new run is selected automatically, unless the judge picked
 * an older run in the last PICK_HOLD_MS (they are reading it: don't pull it away).
 */

import { useCallback, useEffect, useRef, useState } from "react";

export const PICK_HOLD_MS = 10_000;

export interface Selection {
  /** null: follow the latest run. */
  index: number | null;
  pickedAt: number | null;
}

/** The selection after the number of runs went from `before` to `after`. */
export function onRunsChanged(
  selection: Selection,
  before: number,
  after: number,
  now: number,
): Selection {
  if (after <= before || selection.index === null) return selection;
  const holding = selection.pickedAt !== null && now - selection.pickedAt < PICK_HOLD_MS;
  return holding ? selection : { index: null, pickedAt: null };
}

export function useTurnSelection(runs: number): [number | null, (index: number | null) => void] {
  const [selection, setSelection] = useState<Selection>({ index: null, pickedAt: null });
  const previous = useRef(runs);
  useEffect(() => {
    const before = previous.current;
    previous.current = runs;
    setSelection((s) => onRunsChanged(s, before, runs, Date.now()));
  }, [runs]);
  const pick = useCallback(
    (index: number | null) => setSelection({ index, pickedAt: index === null ? null : Date.now() }),
    [],
  );
  return [selection.index, pick];
}
