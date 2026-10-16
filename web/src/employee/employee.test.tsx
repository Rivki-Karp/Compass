import { act, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SessionEvent } from "../api/types";
import { initialSession, reduce } from "../state/session";
import e001Log from "../test/fixtures/e001.json";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { ChatPanel, Thinking } from "./ChatPanel";
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
