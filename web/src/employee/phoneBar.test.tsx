/** The phone summary bar (Day 5 Stage 4): when it shows, what it shows, where it goes. */

import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionEvent } from "../api/types";
import { useMediaQuery } from "../lib/useMediaQuery";
import { initialSession, reduce, type ComparisonState } from "../state/session";
import e001Log from "../test/fixtures/e001.json";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { must } from "../test/views";
import { PhoneBar } from "./PhoneBar";
import { PHONE_QUERY, phoneBarVisible } from "./phoneBarRules";

const walkthrough = walkthroughLog as unknown as SessionEvent[];
const e001 = e001Log as unknown as SessionEvent[];

/** The screen's comparison after the log's events up to (and including) the first match. */
function comparisonAt(log: SessionEvent[], match: (e: SessionEvent) => boolean = () => false) {
  const end = log.findIndex(match);
  return must(log.slice(0, end < 0 ? undefined : end + 1).reduce(reduce, initialSession).comparison);
}

const walkthroughDone = comparisonAt(walkthrough);
const e001Pending = comparisonAt(e001, (e) => e.type === "comparison_ready");
const e001Final = comparisonAt(e001);

describe("phoneBarVisible", () => {
  it("shows only on a phone, with a comparison, outside judges mode", () => {
    const comparison = walkthroughDone;
    expect(phoneBarVisible({ narrow: true, comparison, judges: false })).toBe(true);
    expect(phoneBarVisible({ narrow: false, comparison, judges: false })).toBe(false);
    expect(phoneBarVisible({ narrow: true, comparison: null, judges: false })).toBe(false);
    expect(phoneBarVisible({ narrow: true, comparison, judges: true })).toBe(false);
  });

  it("uses the 700 px breakpoint", () => {
    expect(PHONE_QUERY).toBe("(max-width: 699.98px)");
  });
});

describe("PhoneBar", () => {
  const bar = () => screen.getByTestId("phone-bar");

  it("shows the alternative, the signed diff and no chip for a plain result", () => {
    render(<PhoneBar comparison={walkthroughDone} heroId="hero" />);
    expect(bar()).toHaveTextContent("ויתור על הרכב");
    expect(bar()).toHaveTextContent("+2,914 ₪");
    expect(bar()).not.toHaveTextContent("זמני");
    expect(bar()).not.toHaveTextContent("סופי");
    expect(bar()).toHaveAccessibleName("ויתור על הרכב: פלוס 2,914 שקלים. מעבר לכרטיס התוצאה");
  });

  it("E-001: זמני while pending, סופי once settled", () => {
    expect(e001Pending.view.pending).toBe(true);
    const { rerender } = render(<PhoneBar comparison={e001Pending} heroId="hero" />);
    expect(bar()).toHaveTextContent("ATTO 3");
    expect(bar()).toHaveTextContent("+661 ₪");
    expect(bar()).toHaveTextContent("זמני");
    expect(bar()).toHaveAccessibleName("ATTO 3: פלוס 661 שקלים, זמני. מעבר לכרטיס התוצאה");

    expect(e001Final.settled).toBe(true);
    rerender(<PhoneBar comparison={e001Final as ComparisonState} heroId="hero" />);
    expect(bar()).toHaveTextContent("+611 ₪");
    expect(bar()).toHaveTextContent("סופי");
    expect(bar()).not.toHaveTextContent("זמני");
  });

  it("scrolls to the hero and moves focus there", async () => {
    render(
      <>
        <PhoneBar comparison={walkthroughDone} heroId="hero" />
        <article id="hero" tabIndex={-1} aria-label="תוצאת ההשוואה" />
      </>,
    );
    const hero = screen.getByRole("article");
    const scroll = vi.fn();
    hero.scrollIntoView = scroll;
    await userEvent.setup().click(bar());
    expect(scroll).toHaveBeenCalledWith(expect.objectContaining({ block: "start" }));
    expect(hero).toHaveFocus();
  });
});

describe("useMediaQuery", () => {
  const original = window.matchMedia;
  afterEach(() => {
    window.matchMedia = original;
  });

  it("follows the viewport", () => {
    let matches = false;
    const listeners = new Set<() => void>();
    window.matchMedia = ((query: string) => ({
      media: query,
      get matches() {
        return matches;
      },
      addEventListener: (_: string, fn: () => void) => listeners.add(fn),
      removeEventListener: (_: string, fn: () => void) => listeners.delete(fn),
    })) as unknown as typeof window.matchMedia;

    const { result } = renderHook(() => useMediaQuery(PHONE_QUERY));
    expect(result.current).toBe(false);
    act(() => {
      matches = true;
      listeners.forEach((fn) => fn());
    });
    expect(result.current).toBe(true);
  });

  it("is false where matchMedia does not exist", () => {
    // @ts-expect-error: simulate an environment without matchMedia
    window.matchMedia = undefined;
    const { result } = renderHook(() => useMediaQuery(PHONE_QUERY));
    expect(result.current).toBe(false);
  });
});
