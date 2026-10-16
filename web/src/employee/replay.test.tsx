import { act, render, screen } from "@testing-library/react";
import { useMemo, useReducer, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionEvent } from "../api/types";
import { initialStream, streamReducer, visibleState } from "../state/useSession";
import e001Log from "../test/fixtures/e001.json";
import { type EffectsMemory, EffectsMemoryContext } from "./effects";
import { HeroAnnouncement, HeroCard } from "./HeroCard";
import { SETTLED_FLASH_MS } from "./settle";

const log = e001Log as unknown as SessionEvent[];

let push: (event: SessionEvent) => void = () => {};
let reopen: () => void = () => {};
let switchLayout: () => void = () => {};

/** The page's wiring: the stream reducer, one effects memory, the live region outside the two
 * layouts, the hero inside them (switching remounts it, as the judges toggle does). */
function Page() {
  const [stream, dispatch] = useReducer(streamReducer, initialStream);
  const [judges, setJudges] = useState(false);
  const effects = useMemo<EffectsMemory>(() => ({}), []);
  push = (event) => dispatch({ kind: "event", event });
  reopen = () => dispatch({ kind: "replay" });
  switchLayout = () => setJudges((j) => !j);
  const comparison = visibleState(stream).comparison;
  return (
    <EffectsMemoryContext.Provider value={effects}>
      <HeroAnnouncement comparison={comparison} />
      {comparison ? (
        judges ? (
          <section data-layout="judges">
            <HeroCard comparison={comparison} compact />
          </section>
        ) : (
          <div data-layout="employee">
            <HeroCard comparison={comparison} />
          </div>
        )
      ) : (
        <p>empty</p>
      )}
    </EffectsMemoryContext.Provider>
  );
}

/** Every text the live region showed, and how many times the settle border turned on, sampled
 * after every event and every timer step. */
function watch() {
  const announced: string[] = [];
  let ons = 0;
  let wasOn = false;
  const sample = () => {
    const text = document.querySelector("[aria-live=polite]")?.textContent ?? "";
    if (text && text !== announced[announced.length - 1]) announced.push(text);
    const on =
      document.querySelector("[data-settled-flash]")?.getAttribute("data-settled-flash") === "on";
    if (on && !wasOn) ons += 1;
    wasOn = on;
  };
  return { announced, flashOns: () => ons, sample };
}

let seen: ReturnType<typeof watch>;

function feed(events: SessionEvent[]) {
  for (const event of events) {
    act(() => push(event));
    seen.sample();
  }
}

function wait(ms: number) {
  act(() => vi.advanceTimersByTime(ms));
  seen.sample();
}

describe("a reconnect replays silently", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("E-001, then the stream reopens and replays everything: no second announcement or border", () => {
    render(<Page />);
    seen = watch();
    feed(log);
    wait(SETTLED_FLASH_MS);
    expect(seen.announced).toEqual([
      "ההפרש עודכן: פלוס 661 שקלים",
      "ההשתתפות אושרה על ידי נציג. ההפרש עודכן: פלוס 611 שקלים",
    ]);
    expect(seen.flashOns()).toBe(1);

    // reconnect: the stream starts again from the first event
    act(() => reopen());
    expect(screen.getByText("+611")).toBeInTheDocument(); // the screen keeps what it showed
    feed(log);
    wait(SETTLED_FLASH_MS);
    expect(screen.getByText("+611")).toBeInTheDocument();
    expect(screen.queryByText("empty")).toBeNull(); // never blanked meanwhile
    expect(seen.announced).toHaveLength(2); // nothing new announced
    expect(seen.flashOns()).toBe(1); // no second border
  });

  it("switching layouts (the judges toggle) remounts the hero without its effects", () => {
    render(<Page />);
    seen = watch();
    feed(log);
    wait(SETTLED_FLASH_MS);
    act(() => {
      switchLayout();
      reopen(); // the toggle also reopens the stream with the admin token
    });
    feed(log);
    act(() => switchLayout());
    wait(SETTLED_FLASH_MS);
    expect(seen.announced).toHaveLength(2);
    expect(seen.flashOns()).toBe(1);
    expect(document.querySelector(".motion-ring")).toBeNull(); // no ring on the remounted card
    expect(document.querySelector(".motion-crossfade")).toBeNull();
  });

  it("a new event after the replay is fresh again", () => {
    render(<Page />);
    seen = watch();
    const upToPending = log.findIndex((e) => e.type === "ticket_answered");
    feed(log.slice(0, upToPending));
    act(() => reopen());
    feed(log.slice(0, upToPending)); // replay: silent
    expect(seen.announced).toEqual(["ההפרש עודכן: פלוס 661 שקלים"]);
    feed(log.slice(upToPending)); // the rep answers: live
    expect(seen.announced).toHaveLength(2);
    expect(seen.flashOns()).toBe(1);
    expect(document.querySelector(".motion-ring")).not.toBeNull();
  });
});

describe("streamReducer", () => {
  const events = log.slice(0, 10);

  it("keeps the shown state until the replay has caught up", () => {
    let stream = events.reduce(
      (s, event) => streamReducer(s, { kind: "event", event }),
      initialStream,
    );
    const before = visibleState(stream);
    stream = streamReducer(stream, { kind: "replay" });
    expect(visibleState(stream)).toBe(before);
    for (const event of events.slice(0, -1)) {
      stream = streamReducer(stream, { kind: "event", event });
      expect(visibleState(stream)).toBe(before);
    }
    stream = streamReducer(stream, {
      kind: "event",
      event: events[events.length - 1] as SessionEvent,
    });
    expect(stream.shown).toBeNull();
    expect(visibleState(stream).lastSeq).toBe(before.lastSeq);
  });

  it("a reset (another session) starts empty", () => {
    const stream = streamReducer(
      streamReducer(initialStream, { kind: "event", event: events[0] as SessionEvent }),
      { kind: "reset" },
    );
    expect(stream).toEqual(initialStream);
  });

  it("a first open (nothing shown yet) shows the stream as it arrives", () => {
    const stream = streamReducer(initialStream, { kind: "replay" });
    expect(stream.shown).toBeNull();
  });
});
