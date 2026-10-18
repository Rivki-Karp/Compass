import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { onRunsChanged, PICK_HOLD_MS, useTurnSelection } from "./useTurnSelection";

describe("onRunsChanged", () => {
  const picked = (at: number) => ({ index: 0, pickedAt: at });

  it("following the latest run stays that way", () => {
    expect(onRunsChanged({ index: null, pickedAt: null }, 1, 2, 0)).toEqual({
      index: null,
      pickedAt: null,
    });
  });

  it("an older run picked in the last 10 s is kept when a new run starts", () => {
    expect(onRunsChanged(picked(1000), 2, 3, 1000 + PICK_HOLD_MS - 1)).toEqual(picked(1000));
  });

  it("after 10 s the new run is selected", () => {
    expect(onRunsChanged(picked(1000), 2, 3, 1000 + PICK_HOLD_MS)).toEqual({
      index: null,
      pickedAt: null,
    });
  });

  it("no new run (or a replay from zero): nothing changes", () => {
    expect(onRunsChanged(picked(0), 3, 3, 60_000)).toEqual(picked(0));
    expect(onRunsChanged(picked(0), 3, 0, 60_000)).toEqual(picked(0));
  });
});

describe("useTurnSelection", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("selects a new run, unless the judge just picked an older one", () => {
    const { result, rerender } = renderHook(({ runs }) => useTurnSelection(runs), {
      initialProps: { runs: 2 },
    });
    expect(result.current[0]).toBeNull(); // the latest

    act(() => result.current[1](0)); // the judge picks run 1
    vi.advanceTimersByTime(3_000);
    rerender({ runs: 3 }); // a new run starts 3 s later
    expect(result.current[0]).toBe(0); // still reading run 1

    vi.advanceTimersByTime(PICK_HOLD_MS);
    rerender({ runs: 4 }); // another run, 13 s after the pick
    expect(result.current[0]).toBeNull(); // follows the new run
  });
});
