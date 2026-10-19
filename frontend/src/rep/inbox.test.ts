import { describe, expect, it } from "vitest";
import type { TicketWithView } from "../api/types";
import inboxFixture from "../test/fixtures/e001_inbox.json";
import { initialInbox, reduceInbox, selectedTicket, ticketAge, type InboxAction } from "./inbox";

const [e001] = inboxFixture as unknown as TicketWithView[];
if (!e001) throw new Error("missing in fixture");
const other: TicketWithView = {
  ...e001,
  id: "other",
  created_at: "2026-10-16T09:00:00+00:00",
};

const run = (...actions: InboxAction[]) => actions.reduce(reduceInbox, initialInbox);

describe("reduceInbox", () => {
  it("starts loading, not empty", () => {
    expect(initialInbox.loaded).toBe(false);
    expect(run({ kind: "snapshot", tickets: [] }).loaded).toBe(true);
  });

  it("takes the server's list as is and selects the first ticket", () => {
    const state = run({ kind: "snapshot", tickets: [e001, other] });
    expect(state.tickets.map((t) => t.id)).toEqual([e001.id, "other"]);
    expect(selectedTicket(state)?.view.title).toBe("השתתפות עצמית · ATTO 3");
  });

  it("keeps the selection across snapshots while its ticket is open", () => {
    const state = run(
      { kind: "snapshot", tickets: [e001, other] },
      { kind: "select", ticketId: "other" },
      { kind: "snapshot", tickets: [e001, other] },
    );
    expect(state.selectedId).toBe("other");
  });

  it("ignores a selection of a ticket that isn't in the list", () => {
    const state = run({ kind: "snapshot", tickets: [e001] }, { kind: "select", ticketId: "nope" });
    expect(state.selectedId).toBe(e001.id);
  });

  it("a snapshot that drops the selected ticket moves the selection to the first one", () => {
    const state = run(
      { kind: "snapshot", tickets: [e001, other] },
      { kind: "select", ticketId: "other" },
      { kind: "snapshot", tickets: [e001] },
    );
    expect(state.selectedId).toBe(e001.id);
  });

  it("answering removes the ticket at once, even before the next snapshot", () => {
    const state = run(
      { kind: "snapshot", tickets: [e001] },
      { kind: "answered", ticketId: e001.id },
    );
    expect(state.tickets).toEqual([]);
    expect(state.selectedId).toBeNull();
  });

  it("a late snapshot taken before the answer does not bring the ticket back", () => {
    const state = run(
      { kind: "snapshot", tickets: [e001, other] },
      { kind: "answered", ticketId: e001.id },
      { kind: "snapshot", tickets: [e001, other] },
    );
    expect(state.tickets.map((t) => t.id)).toEqual(["other"]);
  });

  it("after an answer nothing is auto-selected (the rep sees the confirmation)", () => {
    const state = run(
      { kind: "snapshot", tickets: [e001, other] },
      { kind: "answered", ticketId: e001.id },
      { kind: "snapshot", tickets: [other] },
    );
    expect(state.selectedId).toBeNull();
    expect(
      run(
        { kind: "snapshot", tickets: [e001, other] },
        { kind: "answered", ticketId: e001.id },
        { kind: "select", ticketId: "other" },
      ).selectedId,
    ).toBe("other");
  });

  it("new tickets appear live", () => {
    const state = run({ kind: "snapshot", tickets: [] }, { kind: "snapshot", tickets: [e001] });
    expect(state.tickets).toHaveLength(1);
    expect(state.selectedId).toBe(e001.id);
  });

  it("reset clears everything (a new token)", () => {
    const state = run({ kind: "snapshot", tickets: [e001] }, { kind: "reset" });
    expect(state).toEqual(initialInbox);
  });
});

describe("ticketAge", () => {
  const created = "2026-10-16T10:00:00+00:00";
  const at = (minutes: number) => Date.parse(created) + minutes * 60_000;

  it.each([
    [0, "עכשיו"],
    [-1, "עכשיו"], // the browser's clock is a little behind the server's
    [2, "לפני 2 דק'"],
    [59, "לפני 59 דק'"],
    [60, "לפני 1 שע'"],
    [180, "לפני 3 שע'"],
    [24 * 60, "לפני יום"],
    [3 * 24 * 60, "לפני 3 ימים"],
  ])("%i minutes -> %s", (minutes, text) => {
    expect(ticketAge(created, at(minutes))).toBe(text);
  });
});
