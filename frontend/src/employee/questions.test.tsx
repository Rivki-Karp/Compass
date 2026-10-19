import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SessionEvent } from "../api/types";
import { initialSession, reduce, repMessage } from "../state/session";
import questionsLog from "../test/fixtures/questions.json";
import { ChatPanel } from "./ChatPanel";
import { InputsCard } from "./InputsCard";

// A real run (backend/scripts/web_fixtures.py): an occupation question and a free yes/no
// question in one ticket; the rep picks software developer and answers yes with a note.
const log = questionsLog as unknown as SessionEvent[];
const state = log.reduce(reduce, initialSession);
const PARKING = "האם יש חניה לעובדים בבניין המשרדים?";

describe("the employee screen after the rep answered the questions", () => {
  it("the free answer is a 'תשובת הנציג' message, before the agent's reply", () => {
    expect(state.messages.map((m) => m.role)).toEqual(["employee", "assistant", "rep", "assistant"]);
    const rep = state.messages[2];
    expect(rep?.rep).toEqual({
      kind: "answer",
      items: [{ question: PARKING, answer: "כן", note: "בחניון התת-קרקעי, עם תג עובד" }],
    });
  });

  it("renders the bubble with the question, the answer and the note", () => {
    render(
      <ChatPanel
        messages={state.messages}
        turns={state.turns}
        thinking={false}
        suggestions={[]}
        failedText={null}
        onSend={() => {}}
      />,
    );
    const bubble = screen.getByRole("note", { name: "תשובת הנציג" });
    expect(bubble).toHaveTextContent(PARKING);
    expect(within(bubble).getByText("כן")).toBeInTheDocument();
    expect(bubble).toHaveTextContent("בחניון התת-קרקעי, עם תג עובד");
    // the bound answer is not repeated in the chat: it shows in the chips
    expect(bubble).not.toHaveTextContent("מפתח/ת תוכנה");
  });

  it("the bound answer updates the chips: the occupation from the rep, the group from it", () => {
    const view = state.comparison?.view;
    if (!view) throw new Error("no comparison");
    render(<InputsCard view={view} />);
    const inputs = Object.fromEntries(view.inputs.map((i) => [i.id, i]));
    expect(inputs.occupation).toMatchObject({ value: "מפתח/ת תוכנה", source: "representative" });
    expect(inputs.group).toMatchObject({ value: "ב׳", source: "occupation" });
    expect(view.pending).toBe(false);
  });

  it("a note-only part (needs checking) is a 'הערת הנציג'", () => {
    const rep = repMessage({
      ticket_id: "t",
      answer: {},
      fields: {},
      unknown: [],
      partial: true,
      questions: [
        {
          id: "q1",
          kind: "bound",
          bound_field: "occupation",
          prompt_he: "האם 'מפתח AI' נחשב מפתח/ת תוכנה?",
          status: "needs_checking",
          value: null,
          answer: null,
          note: "בודק מול משאבי אנוש",
        },
      ],
    });
    expect(rep?.kind).toBe("note");
    expect(rep?.items[0]?.note).toBe("בודק מול משאבי אנוש");
  });
});
