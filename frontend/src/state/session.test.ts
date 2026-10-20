import { describe, expect, it } from "vitest";
import type { SessionEvent } from "../api/types";
import { EVENT_TYPES } from "../api/generated";
import e001Log from "../test/fixtures/e001.json";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { must } from "../test/views";
import { initialSession, reduce, type SessionState } from "./session";

// Real event logs from a demo-mode run (backend/scripts/web_fixtures.py).
const walkthrough = walkthroughLog as unknown as SessionEvent[];
const e001 = e001Log as unknown as SessionEvent[];

const replay = (events: SessionEvent[], from: SessionState = initialSession) =>
  events.reduce(reduce, from);

const upTo = (events: SessionEvent[], predicate: (e: SessionEvent) => boolean) =>
  events.slice(0, events.findIndex(predicate) + 1);

describe("reduce: the walkthrough", () => {
  const state = replay(walkthrough);

  it("ends with the waiver comparison as the API computed it", () => {
    expect(state.comparison?.view.display_diff).toBe(2914);
    expect(state.comparison?.view.today_net).toBe(11000);
    expect(state.comparison?.view.alternative_net).toBe(13914);
    expect(state.comparison?.origin).toBe("tool");
  });

  it("keeps the conversation in order", () => {
    expect(state.messages.map((m) => m.role)).toEqual([
      "employee",
      "assistant",
      "employee",
      "assistant",
    ]);
    expect(state.messages[3]?.text).toContain("+2,914");
    expect(state.messages[3]?.turn).toBe(1);
  });

  it("groups tool activity per turn", () => {
    expect(state.turns).toHaveLength(2);
    expect(state.turns[1]?.tools.map((t) => [t.name, t.ok])).toEqual([
      ["save_profile", true],
      ["lookup_vehicle", true],
      ["set_current_situation", true],
      ["compare", true],
    ]);
    expect(state.turns[1]?.finished?.outcome).toBe("reply");
  });

  it("stops thinking when the run finishes", () => {
    expect(state.thinking).toBe(false);
    const midRun = replay(upTo(walkthrough, (e) => e.type === "agent_started"));
    expect(midRun.thinking).toBe(true);
    expect(midRun.thinkingSince).not.toBeNull();
  });

  it("is idempotent: replaying any prefix again changes nothing", () => {
    for (const cut of [1, 5, walkthrough.length]) {
      expect(replay(walkthrough.slice(0, cut), state)).toBe(state);
    }
    expect(replay(walkthrough, replay(walkthrough))).toEqual(state);
  });
});

describe("reduce: E-001 pending, then final", () => {
  const answered = e001.findIndex((e) => e.type === "ticket_answered");
  const beforeAnswer = replay(e001.slice(0, answered));
  const after = replay(e001);

  it("shows +661 pending while the ticket is open", () => {
    expect(beforeAnswer.comparison?.view.display_diff).toBe(661);
    expect(beforeAnswer.comparison?.view.pending).toBe(true);
    expect(beforeAnswer.comparison?.settled).toBe(false);
    expect(beforeAnswer.openTickets).toHaveLength(1);
    expect(beforeAnswer.status).toBe("waiting_for_rep");
  });

  it("settles to +611 after the representative answers", () => {
    expect(after.comparison?.view.display_diff).toBe(611);
    expect(after.comparison?.view.pending).toBe(false);
    expect(after.comparison?.settled).toBe(true);
    expect(after.openTickets).toEqual([]);
    expect(after.status).toBe("active");
    const participation = after.comparison?.view.inputs.find(
      (i) => i.id === "alternative_participation",
    );
    expect(participation?.source).toBe("representative");
  });

  it("records the rep resume as its own turn", () => {
    expect(after.turns.map((t) => t.trigger)).toEqual([
      "employee_turn",
      "employee_turn",
      "employee_turn",
      "rep_answer",
    ]);
  });
});

describe("reduce: every event kind", () => {
  const base = { session_id: "s", created_at: "2026-10-15T00:00:00Z" };
  let seq = 0;
  const ev = (type: string, payload: unknown) =>
    ({ ...base, seq: ++seq, type, payload }) as SessionEvent;

  it("handles each type the server can send", () => {
    const events: SessionEvent[] = [
      ev("session_created", { status: "active" }),
      ev("user_message", { message_seq: 1, content: { text: "היי" } }),
      ev("agent_started", { trigger: "employee_turn" }),
      ev("tool_call", { tool_use_id: "t1", name: "get_rule" }),
      ev("tool_result", { tool_use_id: "t1", name: "get_rule", ok: false }),
      ev("profile_updated", { fields: {} }),
      ev("current_situation_set", { scenario: {} }),
      ev("guard_check", { passed: true, action: "accept" }),
      ev("agent_error", { kind: "timeout" }),
      ev("assistant_message", {
        message_seq: 2,
        text: "שגיאה",
        kind: "error",
        comparison_ref: null,
      }),
      ev("agent_finished", { outcome: "error" }),
      // the payslip upload: kept for judges mode, nothing on screen yet
      ev("payslip_extracted", { fields: {}, dropped_keys: 0 }),
      ev("payslip_failed", { code: "payslip_unavailable" }),
      ev("payslip_confirmed", {
        candidate_seq: 1,
        applied: {},
        kept_representative: [],
        waiting_for_rep: [],
        car_hint: null,
      }),
      ev("current_car_picked", { outcome: "no_car" }),
      ev("session_status", { status: "closed" }),
    ];
    const kinds = new Set(events.map((e) => e.type));
    const covered = new Set([
      ...kinds,
      "comparison_ready",
      "comparison_set_ready", // options.test.tsx replays a real one
      "current_car_offered", // carPicker.test.tsx
      "ticket_opened",
      "ticket_answered",
    ]);
    expect([...EVENT_TYPES].every((t) => covered.has(t))).toBe(true); // the rest: fixtures above

    const state = replay(events);
    expect(state.turns[0]?.tools).toEqual([{ toolUseId: "t1", name: "get_rule", ok: false }]);
    expect(state.turns[0]?.events.map((e) => e.type)).toContain("guard_check");
    expect(state.lastError).toBe("timeout");
    expect(state.messages.at(-1)?.kind).toBe("error");
    expect(state.thinking).toBe(false);
    expect(state.status).toBe("closed");
    expect(state.lastSeq).toBe(seq);
    expect(state.between.map((e) => e.type)).toContain("payslip_extracted");
  });
});

describe("the representative's note", () => {
  const answered = e001.findIndex((e) => e.type === "ticket_answered");
  const withNote = (answer: unknown): SessionEvent[] =>
    e001.map((e, i) =>
      i === answered && e.type === "ticket_answered"
        ? { ...e, payload: { ...e.payload, answer } }
        : e,
    );

  it("a ticket answer with text adds the rep's note to the chat, before the reply", () => {
    const state = replay(
      withNote({
        text: "  מעודכן מנובמבר, 400 ₪ אחרי השנה הראשונה  ",
        values: {},
      }),
    );
    const notes = state.messages.filter((m) => m.role === "rep");
    expect(notes).toEqual([
      {
        seq: must(e001[answered]).seq,
        role: "rep",
        text: "מעודכן מנובמבר, 400 ₪ אחרי השנה הראשונה",
        kind: null,
        turn: null,
        rep: {
          kind: "note",
          items: [{ question: null, answer: null, note: "מעודכן מנובמבר, 400 ₪ אחרי השנה הראשונה" }],
        },
      },
    ]);
    const index = state.messages.findIndex((m) => m.role === "rep");
    expect(state.messages[index + 1]?.role).toBe("assistant"); // the model's reply follows
  });

  it("no text, no note", () => {
    expect(replay(e001).messages.some((m) => m.role === "rep")).toBe(false);
    expect(replay(withNote({ text: "   " })).messages.some((m) => m.role === "rep")).toBe(false);
  });
});

describe("each alternative settles on its own", () => {
  const view = (car: string, pending: boolean, diff: number) =>
    ({ alternative_kind: "car", alternative_car_id: car, pending, display_diff: diff }) as never;
  const ready = (seq: number, car: string, pending: boolean, diff: number) =>
    ({
      session_id: "s",
      seq,
      type: "comparison_ready",
      created_at: "",
      payload: {
        alternative_kind: "car",
        alternative: {},
        view: view(car, pending, diff),
        pending_rep: pending,
      },
    }) as unknown as SessionEvent;

  it("a car's final comparison settles that car, whatever came in between", () => {
    const state = replay([
      ready(1, "CAR-10", true, 661),
      ready(2, "CAR-06", true, 1020),
      ready(3, "CAR-10", false, 611), // the rep answered ATTO 3 only
    ]);
    expect(state.comparisons["car:CAR-10"]?.settled).toBe(true);
    expect(state.comparisons["car:CAR-10"]?.settledSeq).toBe(3);
    expect(state.comparisons["car:CAR-06"]?.settled).toBe(false);
    expect(state.comparisons["car:CAR-06"]?.view.pending).toBe(true);
  });

  it("a partial answer keeps the ticket open", () => {
    const opened = {
      session_id: "s",
      seq: 1,
      type: "ticket_opened",
      created_at: "",
      payload: { ticket: { id: "t1" } },
    } as unknown as SessionEvent;
    const answered = (seq: number, partial: boolean) =>
      ({
        session_id: "s",
        seq,
        type: "ticket_answered",
        created_at: "",
        payload: { ticket_id: "t1", answer: {}, fields: {}, unknown: [], partial },
      }) as unknown as SessionEvent;
    expect(replay([opened, answered(2, true)]).openTickets).toHaveLength(1);
    expect(replay([opened, answered(2, true), answered(3, false)]).openTickets).toHaveLength(0);
  });
});
