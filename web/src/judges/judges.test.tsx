import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import type { JudgesStats, SessionEvent } from "../api/types";
import { initialSession, reduce } from "../state/session";
import e001Log from "../test/fixtures/e001.json";
import guardRetryLog from "../test/fixtures/guard_retry.json";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { must } from "../test/views";
import { engineCards, guardVerdict } from "./engine";
import { EngineRoom } from "./EngineRoom";
import { StatsGrid } from "./Summary";

const replay = (log: unknown) => (log as SessionEvent[]).reduce(reduce, initialSession);
const walkthrough = replay(walkthroughLog);
const guardRetry = replay(guardRetryLog);
const e001 = replay(e001Log);

/** What the stream sends without the admin token: the redacted fields are gone. */
function redacted(log: unknown): SessionEvent[] {
  return (log as SessionEvent[]).map((e) => {
    if (e.type === "tool_call") return { ...e, payload: { ...e.payload, input: undefined } };
    if (e.type === "tool_result") {
      const { tool_use_id, name, ok } = e.payload;
      return { ...e, payload: { tool_use_id, name, ok } };
    }
    if (e.type === "guard_check") {
      return { ...e, payload: { passed: e.payload.passed, action: e.payload.action } };
    }
    return e;
  }) as SessionEvent[];
}

describe("engineCards", () => {
  it("the walkthrough's comparison turn: tools in order, the result, the guard", () => {
    const cards = engineCards(must(walkthrough.turns[1]));
    expect(cards.map((c) => (c.kind === "tool" ? `tool:${c.name}` : c.kind))).toEqual([
      "tool:save_profile",
      "tool:lookup_vehicle",
      "tool:set_current_situation",
      "tool:compare",
      "comparison",
      "guard",
    ]);
    const compare = must(cards.find((c) => c.kind === "tool" && c.name === "compare"));
    if (compare.kind !== "tool") throw new Error();
    expect(compare.ok).toBe(true);
    expect(compare.input).toEqual({ alternative: { kind: "waiver" } });
    expect(compare.result).toMatchObject({ ok: true }); // the full result, from the DB
    const guard = must(cards.find((c) => c.kind === "guard"));
    if (guard.kind !== "guard") throw new Error();
    expect(guardVerdict(guard.guard)).toBe("3 מתוך 3 אומתו · נשלח");
    expect(guard.guard.sources).toMatchObject({ "+2,914": "compare" });
  });

  it("a guard rejection: the retry with the struck draft, then the accepted rewrite", () => {
    const guards = engineCards(must(guardRetry.turns[1])).flatMap((c) =>
      c.kind === "guard" ? [c.guard] : [],
    );
    expect(guards.map((g) => g.action)).toEqual(["retry", "accept_after_retry"]);
    const [rejected, accepted] = guards.map(must);
    expect(rejected?.violations).toEqual(["+2,915"]);
    expect(rejected?.rejected_draft).toContain("+2,915");
    expect(guardVerdict(must(rejected))).toBe("2 מתוך 3 אומתו · נדחה, המודל מנסח מחדש בלי כלים");
    expect(guardVerdict(must(accepted))).toBe("3 מתוך 3 אומתו · נשלח אחרי ניסוח מחדש");
  });

  it("the rep-answer run starts with the answer and the server's settle (no model call)", () => {
    const run = must(e001.turns.find((t) => t.trigger === "rep_answer"));
    const cards = engineCards(run);
    expect(cards[0]).toMatchObject({
      kind: "rep_answer",
      values: { "alternative_participation:CAR-10": 350 },
    });
    expect(cards[1]).toMatchObject({ kind: "comparison", origin: "server" });
    if (cards[1]?.kind !== "comparison") throw new Error();
    expect(cards[1].view.display_diff).toBe(611);
    expect(cards.filter((c) => c.kind === "tool").map((c) => c.kind === "tool" && c.name)).toEqual([
      "compare",
    ]);
  });

  it("the template verdict", () => {
    expect(
      guardVerdict({ passed: false, action: "template", numbers: ["1"], violations: ["1"] }),
    ).toBe("0 מתוך 1 אומתו · נדחה שוב, נשלחה תשובה מתבנית");
    expect(guardVerdict({ passed: true, action: "accept", numbers: [], violations: [] })).toBe(
      "אין מספרים בתשובה · נשלח",
    );
  });

  it("without the admin token the cards carry no inputs, results or numbers", () => {
    const state = (redacted(guardRetryLog) as SessionEvent[]).reduce(reduce, initialSession);
    const cards = engineCards(must(state.turns[1]));
    for (const card of cards) {
      if (card.kind === "tool") expect([card.input, card.result]).toEqual([null, null]);
      if (card.kind === "guard") expect(card.guard.numbers).toBeUndefined();
    }
  });
});

describe("reduce: events between runs", () => {
  it("the rep's answer and the server's settle go to the next run, not to the previous one", () => {
    const [ask, answer] = e001.turns.slice(-2).map(must);
    expect(ask?.events.some((e) => e.type === "ticket_answered")).toBe(false);
    expect(answer?.before.map((e) => e.type)).toEqual([
      "ticket_answered",
      "session_status",
      "comparison_ready",
    ]);
    expect(e001.between).toEqual([]);
  });
});

function Room({ turns }: { turns: typeof guardRetry.turns }) {
  const [selected, setSelected] = useState<number | null>(null);
  return <EngineRoom turns={turns} selected={selected} onSelect={setSelected} />;
}

describe("EngineRoom", () => {
  it("shows the latest run: stats pills, tool cards, the rejected draft struck through", () => {
    render(<Room turns={guardRetry.turns} />);
    expect(screen.getByRole("heading")).toHaveTextContent("חדר המנועים · תור 2");
    const pills = screen.getByRole("list", { name: "נתוני התור" });
    expect(pills).toHaveTextContent("rounds 2");
    expect(pills).toHaveTextContent("cost — (demo)");
    expect(screen.getAllByText("המודל קרא לכלי")).toHaveLength(4);
    const draft = must(document.querySelector(".line-through"));
    expect(draft.textContent).toContain("+2,915");
    const numbers = screen.getAllByRole("list", { name: "המספרים בתשובה" });
    expect(within(must(numbers[0])).getByText(/אין מקור/)).toHaveTextContent("+2,915");
    expect(within(must(numbers[1])).getByText("+2,914").parentElement).toHaveTextContent(
      "+2,914 ✓ compare",
    );
  });

  it("the turn selector switches runs", async () => {
    render(<Room turns={guardRetry.turns} />);
    await userEvent.setup().selectOptions(screen.getByRole("combobox"), "0");
    expect(screen.getByRole("heading")).toHaveTextContent("חדר המנועים · תור 1");
    expect(screen.getByText("1 מתוך 1 אומתו · נשלח")).toBeInTheDocument();
  });

  it("before any run: a quiet line", () => {
    render(<Room turns={[]} />);
    expect(screen.getByText(/כאן יופיעו קריאות הכלים/)).toBeInTheDocument();
  });
});

describe("StatsGrid", () => {
  const stats: JudgesStats = {
    evals: {
      run_at: "2026-10-15 14:02 UTC",
      model: "claude-sonnet-5-5",
      effort: "low",
      repeat: 3,
      scenarios_passed: 15,
      scenarios_total: 15,
      runs_passed: 45,
      runs_total: 45,
    },
    spend: { total_usd: "2.33", calls: 62, cap_usd: "30.00" },
    tests: { pytest: 567, vitest: 120, as_of: "2026-10-16" },
    cost_per_conversation: { usd: "0.0252", runs: 45 },
  };

  it("shows the server's values as they are", () => {
    render(<StatsGrid stats={stats} />);
    expect(screen.getByText("15/15")).toBeInTheDocument();
    expect(screen.getByText("$2.33")).toBeInTheDocument();
    const grid = screen.getByRole("region", { name: "נתונים" });
    expect(grid).toHaveTextContent("מתוך תקרה של $30.00 · 62 ריצות");
    expect(grid).toHaveTextContent("claude-sonnet-5-5 · low");
    expect(grid).toHaveTextContent("pytest + vitest · נכון ל-2026-10-16");
    expect(screen.getByText("567 + 120")).toBeInTheDocument();
    expect(screen.getByText("$0.0252")).toBeInTheDocument();
  });

  it("a missing part is a dash, never a made-up number", () => {
    render(<StatsGrid stats={{ ...stats, spend: null, tests: null }} />);
    expect(screen.getAllByText("—")).toHaveLength(2);
    expect(screen.getAllByText("אין נתון")).toHaveLength(2);
  });
});
