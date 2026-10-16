import { act, render, screen } from "@testing-library/react";
import { useReducer } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionEvent } from "../api/types";
import { initialSession, reduce, type SessionState } from "../state/session";
import e001Log from "../test/fixtures/e001.json";
import { must } from "../test/views";
import { HeroAnnouncement, HeroCard } from "./HeroCard";
import { InputsCard } from "./InputsCard";
import { SETTLED_FLASH_MS } from "./settle";

/** The real E-001 log, fed event by event into the real reducer, as the stream does. */
const log = e001Log as unknown as SessionEvent[];
const answeredAt = log.findIndex((e) => e.type === "ticket_answered");

let push: (event: SessionEvent) => void = () => {};

function Screen() {
  const [state, dispatch] = useReducer(
    (s: SessionState, e: SessionEvent) => reduce(s, e),
    initialSession,
  );
  push = dispatch;
  const comparison = state.comparison;
  return (
    <>
      <HeroAnnouncement comparison={comparison} />
      {comparison ? (
        <>
          <HeroCard comparison={comparison} />
          <InputsCard view={comparison.view} />
        </>
      ) : null}
    </>
  );
}

const flash = () =>
  document.querySelector("[data-settled-flash]")?.getAttribute("data-settled-flash");
const altRow = () => document.querySelector('[data-input="alternative_participation"]');

describe("pending -> final on the real E-001 event log", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("goes from +661 pending to +611 final, with the 2 s border and the announcement", () => {
    render(<Screen />);
    act(() => log.slice(0, answeredAt).forEach((e) => push(e)));

    // pending (§4.4)
    expect(screen.getByText("+661")).toBeInTheDocument();
    expect(screen.getByText("זמני")).toBeInTheDocument();
    expect(screen.queryByText("סופי")).toBeNull();
    expect(altRow()?.querySelector('[data-source="pending_rep"]')).not.toBeNull();
    expect(altRow()).toHaveClass("border-dashed");
    expect(flash()).toBe("off");
    expect(screen.getByText("ההפרש עודכן: פלוס 661 שקלים")).toBeInTheDocument();

    // the rep answers; the employee stream gets ticket_answered, then the new comparison
    const settledAt = log.findIndex((e, i) => i > answeredAt && e.type === "comparison_ready");
    act(() => log.slice(answeredAt, settledAt).forEach((e) => push(e)));
    expect(screen.getByText("+661")).toBeInTheDocument(); // nothing final before the server says so
    act(() => push(must(log[settledAt])));

    // final
    expect(screen.getByText("+611")).toBeInTheDocument();
    expect(screen.queryByText("+661")).toBeNull();
    expect(screen.getByText("סופי")).toBeInTheDocument();
    expect(screen.queryByText("זמני")).toBeNull();
    expect(screen.queryByText("ממתינה לנציג")).toBeNull();
    expect(altRow()?.querySelector('[data-source="representative"]')).toHaveTextContent(
      "אושר על ידי נציג",
    );
    expect(altRow()).not.toHaveClass("border-dashed");
    expect(document.querySelector(".opacity-75")).toBeNull();
    expect(document.querySelector(".border-dashed")).toBeNull();
    expect(
      screen.getByText("ההשתתפות אושרה על ידי נציג. ההפרש עודכן: פלוס 611 שקלים"),
    ).toBeInTheDocument();

    // the up border for 2 s, then gone; the chip stays
    expect(flash()).toBe("on");
    act(() => vi.advanceTimersByTime(SETTLED_FLASH_MS - 1));
    expect(flash()).toBe("on");
    act(() => vi.advanceTimersByTime(1));
    expect(flash()).toBe("off");
    expect(screen.getByText("סופי")).toBeInTheDocument();

    // the rest of the log (the reply, agent_finished) changes nothing on the card
    act(() => log.slice(settledAt + 1).forEach((e) => push(e)));
    expect(screen.getByText("סופי")).toBeInTheDocument();
    expect(flash()).toBe("off");
  });

  it("a later, unrelated comparison is not 'final' and does not flash", () => {
    render(<Screen />);
    act(() => log.forEach((e) => push(e)));
    act(() => vi.advanceTimersByTime(SETTLED_FLASH_MS));
    const last = must([...log].reverse().find((e) => e.type === "comparison_ready"));
    const seq = must(log[log.length - 1]).seq + 1;
    act(() => push({ ...last, seq } as SessionEvent));
    expect(screen.queryByText("סופי")).toBeNull();
    expect(flash()).toBe("off");
    expect(screen.getByText("ההפרש עודכן: פלוס 611 שקלים")).toBeInTheDocument();
  });
});
