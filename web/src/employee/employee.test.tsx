import { act, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SessionEvent } from "../api/types";
import { initialSession, reduce } from "../state/session";
import e001Log from "../test/fixtures/e001.json";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { ChatPanel, Thinking } from "./ChatPanel";
import { EmptyComparison } from "./EmptyComparison";
import { HeroAnnouncement, HeroCard } from "./HeroCard";
import { InputsCard } from "./InputsCard";

function must<T>(value: T | null | undefined): T {
  if (value === null || value === undefined) throw new Error("missing in fixture");
  return value;
}

const walkthrough = (walkthroughLog as unknown as SessionEvent[]).reduce(reduce, initialSession);
const e001 = e001Log as unknown as SessionEvent[];
const e001Pending = e001
  .slice(0, e001.findIndex((e) => e.type === "ticket_answered"))
  .reduce(reduce, initialSession);

describe("HeroCard: the walkthrough", () => {
  const comparison = must(walkthrough.comparison);

  it("shows the API's difference, nets and group pill", () => {
    render(<HeroCard comparison={comparison} />);
    expect(screen.getByRole("heading")).toHaveTextContent("ויתור על הרכב לעומת היום");
    expect(screen.getByText("+2,914")).toBeInTheDocument();
    expect(screen.getByText("11,000")).toBeInTheDocument();
    expect(screen.getByText("13,914")).toBeInTheDocument();
    expect(document.body.textContent).toContain("קבוצה ב׳ · תקציב 3,700 ₪");
    expect(screen.getByText("יותר בנטו, בכל חודש")).toBeInTheDocument();
    expect(screen.getByText(/COROLLA CROSS 2025/)).toBeInTheDocument();
  });

  it("renders the current_car_above_group warning with the API's Hebrew message", () => {
    render(<HeroCard comparison={comparison} />);
    const warnings = screen.getByRole("list", { name: "אזהרות" });
    const message = must(comparison.view.warnings[0]).message;
    expect(within(warnings).getByText(message)).toBeInTheDocument();
    expect(message).toContain("מעל קבוצה ב׳");
  });

  it("announces the update to screen readers", () => {
    render(<HeroAnnouncement comparison={comparison} />);
    expect(screen.getByText("ההפרש עודכן: פלוס 2,914 שקלים")).toBeInTheDocument();
  });
});

describe("HeroCard: E-001 pending", () => {
  it("marks the provisional result: pending chip, זמני, dimmed, dashed alternative", () => {
    const { container } = render(<HeroCard comparison={must(e001Pending.comparison)} />);
    expect(screen.getByText("+661")).toBeInTheDocument();
    expect(screen.getByText("ממתינה לנציג")).toBeInTheDocument();
    expect(screen.getByText("זמני")).toBeInTheDocument();
    expect(container.querySelector(".opacity-75")).not.toBeNull();
    expect(container.querySelector(".border-dashed")).not.toBeNull();
  });

  it("shows the pending input with the catalog default, chip and dashed border", () => {
    const { container } = render(<InputsCard view={must(e001Pending.comparison).view} />);
    const row = must(container.querySelector<HTMLElement>("[data-input=alternative_participation]"));
    expect(row.className).toContain("border-dashed");
    expect(within(row).getByText("ממתינה לנציג")).toBeInTheDocument();
    expect(row.textContent).toContain("300");
  });
});

describe("InputsCard", () => {
  it("gives every displayed input a source chip", () => {
    const { container } = render(<InputsCard view={must(walkthrough.comparison).view} />);
    const rows = container.querySelectorAll("[data-input]");
    expect(rows.length).toBe(must(walkthrough.comparison).view.inputs.length);
    rows.forEach((row) => expect(row.querySelector("[data-source]")).not.toBeNull());
  });
});

describe("ChatPanel", () => {
  it("shows each turn's tools after its reply", () => {
    render(
      <ChatPanel
        messages={walkthrough.messages}
        turns={walkthrough.turns}
        thinking={false}
        suggestions={[]}
        failedText={null}
        onSend={() => {}}
      />,
    );
    const rows = screen.getAllByRole("list", { name: "כלים שהופעלו" });
    expect(rows).toHaveLength(2);
    expect(rows[1]).toHaveTextContent("compare ✓");
  });

  it("offers a retry when a message could not be sent", () => {
    const onSend = vi.fn();
    render(
      <ChatPanel
        messages={[]}
        turns={[]}
        thinking={false}
        suggestions={[]}
        failedText="שלום"
        onSend={onSend}
      />,
    );
    act(() => screen.getByRole("button", { name: /נסו שוב/ }).click());
    expect(onSend).toHaveBeenCalledWith("שלום");
  });

  it("shows the representative's note as the rep's, not the advisor's", () => {
    render(
      <ChatPanel
        messages={[{ seq: 9, role: "rep", text: "מנובמבר", kind: null, turn: null }]}
        turns={[]}
        thinking={false}
        suggestions={[]}
        failedText={null}
        onSend={() => {}}
      />,
    );
    const note = screen.getByRole("note", { name: "הערת הנציג" });
    expect(note).toHaveTextContent("הערת הנציג");
    expect(note).toHaveTextContent("מנובמבר");
  });
});

describe("Thinking", () => {
  it("adds 'עדיין עובד על זה' after 8 seconds", () => {
    vi.useFakeTimers();
    render(
      <ol>
        <Thinking />
      </ol>,
    );
    expect(screen.getByText(/מחשב…/)).toBeInTheDocument();
    expect(screen.queryByText(/עדיין עובד על זה/)).toBeNull();
    act(() => vi.advanceTimersByTime(8000));
    expect(screen.getByText(/עדיין עובד על זה/)).toBeInTheDocument();
    vi.useRealTimers();
  });
});

describe("EmptyComparison", () => {
  it("explains how it works in three steps, with no numbers", () => {
    const { container } = render(<EmptyComparison />);
    expect(screen.getByRole("heading")).toHaveTextContent("איך זה עובד");
    const steps = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(steps.map((s) => s.textContent?.replace(/^\d/, ""))).toEqual([
      "ספרו על התפקיד, השכר והרכב",
      "הכלים מחשבים את הנטו בדיוק",
      "כל מספר מגיע עם המקור שלו",
    ]);
    // the step numbers are decoration (aria-hidden); no amount anywhere
    const visible = [...container.querySelectorAll("li > span:not([aria-hidden])")];
    expect(visible.map((e) => e.textContent).join(" ")).not.toMatch(/\d/);
    expect(container.querySelector("[data-direction='empty']")).not.toBeNull();
  });
});

describe("HeroCard: the alternative's drive and group", () => {
  it("shows the API's details under a catalog car, nothing for a waiver", () => {
    const { unmount } = render(<HeroCard comparison={must(e001Pending.comparison)} />);
    expect(screen.getByText("חשמלי · קבוצה ג׳")).toBeInTheDocument();
    unmount();
    render(<HeroCard comparison={must(walkthrough.comparison)} />);
    expect(must(walkthrough.comparison).view.alternative_details).toBeNull();
    expect(screen.queryByText(/ · קבוצה/)).toBeNull();
  });
});

describe("ChatPanel: newest message in view", () => {
  it("scrolls the message list, never the page", () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    const props = {
      turns: walkthrough.turns,
      thinking: false,
      suggestions: [],
      failedText: null,
      onSend: () => {},
    };
    const { rerender } = render(
      <ChatPanel messages={walkthrough.messages.slice(0, 1)} {...props} />,
    );
    const ol = document.querySelector("ol[aria-live]") as HTMLOListElement;
    Object.defineProperty(ol, "scrollHeight", { configurable: true, value: 900 });
    rerender(<ChatPanel messages={walkthrough.messages} {...props} />);
    expect(ol.scrollTop).toBe(900);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});
