import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TicketWithView } from "../api/types";
import negative from "../test/fixtures/e001_answer_negative.json";
import inboxFixture from "../test/fixtures/e001_inbox.json";
import { must } from "../test/views";
import { TicketDetail } from "./TicketDetail";
import { TicketList } from "./TicketList";

const ticket = must((inboxFixture as unknown as TicketWithView[])[0]);

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

function renderDetail(onAnswered = vi.fn(), onReauth = vi.fn()) {
  render(<TicketDetail ticket={ticket} token="rep" onAnswered={onAnswered} onReauth={onReauth} />);
  return { onAnswered, onReauth };
}

describe("TicketDetail: the E-001 ticket from the real inbox", () => {
  it("shows the question, context and the three tiles from the ticket view", () => {
    renderDetail();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "מה גובה ההשתתפות העצמית החודשית ב-ATTO 3?",
    );
    expect(screen.getByText("מנהל/ת מוצר · קבוצה ג׳ · היום: COROLLA CROSS")).toBeInTheDocument();
    expect(screen.getByText("CAR-10")).toBeInTheDocument();
    expect(screen.getByText("300")).toBeInTheDocument(); // catalog default
    expect(screen.getByText("+661")).toBeInTheDocument(); // the employee's provisional diff
    expect(screen.getByText("זמני, לפי ברירת המחדל")).toBeInTheDocument();
    expect(screen.getByLabelText("סכום ההשתתפות החודשית (₪)")).toBeInTheDocument();
  });

  it("sends the value as typed and shows the server's Hebrew error next to the field", async () => {
    const fetchMock = respond(422, negative);
    vi.stubGlobal("fetch", fetchMock);
    const { onAnswered } = renderDetail();
    const user = userEvent.setup();
    const input = screen.getByLabelText("סכום ההשתתפות החודשית (₪)");
    await user.type(input, "-50");
    await user.click(screen.getByRole("button", { name: "אישור ושליחה לעובד/ת" }));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/tickets/${ticket.id}/answer`);
    expect(JSON.parse(String(init.body))).toEqual({
      values: { "alternative_participation:CAR-10": "-50" },
    });
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer rep");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("הערך צריך להיות בין 0 ל-20,000.");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", alert.id);
    expect(document.body.textContent).not.toContain("must be"); // the English detail
    expect(onAnswered).not.toHaveBeenCalled();
  });

  it("a 200 reports the ticket answered", async () => {
    vi.stubGlobal("fetch", respond(200, { ...ticket, status: "answered" }));
    const { onAnswered } = renderDetail();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("סכום ההשתתפות החודשית (₪)"), "350");
    await user.click(screen.getByRole("button", { name: "אישור ושליחה לעובד/ת" }));
    await vi.waitFor(() => expect(onAnswered).toHaveBeenCalledWith(ticket.id));
  });

  it("a refused token asks for it again", async () => {
    vi.stubGlobal("fetch", respond(401, { detail: "invalid token" }));
    const { onReauth } = renderDetail();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("סכום ההשתתפות החודשית (₪)"), "350");
    await user.click(screen.getByRole("button", { name: "אישור ושליחה לעובד/ת" }));
    await vi.waitFor(() => expect(onReauth).toHaveBeenCalled());
    expect(screen.getByRole("alert")).toHaveTextContent("טוקן הנציג לא תקף יותר");
  });
});

describe("TicketList", () => {
  const now = Date.parse(ticket.created_at) + 2 * 60_000;

  it("shows a link row per ticket with title, age and field id, and the count", () => {
    render(
      <TicketList tickets={[ticket]} loaded selectedId={ticket.id} now={now} onSelect={vi.fn()} />,
    );
    const link = screen.getByRole("link", { name: /השתתפות עצמית · ATTO 3/ });
    expect(link).toHaveAttribute("aria-current", "true");
    expect(link).toHaveTextContent("לפני 2 דק'");
    expect(link).toHaveTextContent("alternative_participation:CAR-10");
    expect(screen.getByLabelText("1 טיקטים פתוחים")).toBeInTheDocument();
  });

  it("selecting a row does not navigate", async () => {
    const onSelect = vi.fn();
    render(
      <TicketList tickets={[ticket]} loaded selectedId={null} now={now} onSelect={onSelect} />,
    );
    await userEvent.setup().click(screen.getByRole("link"));
    expect(onSelect).toHaveBeenCalledWith(ticket.id);
  });

  it("empty: the §4.6 text once loaded", () => {
    const { rerender } = render(
      <TicketList tickets={[]} loaded={false} selectedId={null} now={now} onSelect={vi.fn()} />,
    );
    expect(screen.getByText("טוען טיקטים…")).toBeInTheDocument();
    rerender(<TicketList tickets={[]} loaded selectedId={null} now={now} onSelect={vi.fn()} />);
    expect(screen.getByText("טיקטים חדשים יופיעו כאן אוטומטית")).toBeInTheDocument();
  });
});
