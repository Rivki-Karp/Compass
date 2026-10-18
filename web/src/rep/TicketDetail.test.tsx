import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TicketFieldView, TicketWithView } from "../api/types";
import negative from "../test/fixtures/e001_answer_negative.json";
import inboxFixture from "../test/fixtures/e001_inbox.json";
import { must } from "../test/views";
import { TicketDetail } from "./TicketDetail";
import { TicketList } from "./TicketList";

const ticket = must((inboxFixture as unknown as TicketWithView[])[0]);
const ATTO = "alternative_participation:CAR-10";
const SEND = { name: "אישור ושליחה לעובד/ת" };
const ATTO_INPUT = "סכום ההשתתפות החודשית ב-ATTO 3 (₪)";

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

function renderDetail(t: TicketWithView = ticket, onAnswered = vi.fn(), onReauth = vi.fn()) {
  render(<TicketDetail ticket={t} token="rep" onAnswered={onAnswered} onReauth={onReauth} />);
  return { onAnswered, onReauth };
}

function sentBody(fetchMock: ReturnType<typeof vi.fn>): unknown {
  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return JSON.parse(String(init.body));
}

describe("TicketDetail: the E-001 ticket from the real inbox", () => {
  it("titles it from its fields; the model's question is secondary", () => {
    renderDetail();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("השתתפות עצמית · ATTO 3");
    expect(screen.getByText(ticket.question)).toHaveClass("line-clamp-3");
    expect(screen.getByText("מנהל/ת מוצר · קבוצה ג׳ · היום: COROLLA CROSS")).toBeInTheDocument();
    const section = screen.getByRole("region", { name: /ATTO 3/ });
    expect(within(section).getByText("CAR-10")).toBeInTheDocument();
    expect(within(section).getByText("300")).toBeInTheDocument(); // catalog default
    expect(within(section).getByText("+661")).toBeInTheDocument(); // this car's provisional diff
    expect(within(section).getByText("זמני, לפי ברירת המחדל")).toBeInTheDocument();
    expect(screen.getByLabelText(ATTO_INPUT)).toHaveValue(""); // nothing prefilled
  });

  it("sends the value as typed and shows the server's Hebrew error next to the field", async () => {
    const fetchMock = respond(422, negative);
    vi.stubGlobal("fetch", fetchMock);
    const { onAnswered } = renderDetail();
    const user = userEvent.setup();
    const input = screen.getByLabelText(ATTO_INPUT);
    await user.type(input, "-50");
    await user.click(screen.getByRole("button", SEND));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/tickets/${ticket.id}/answer`);
    expect(sentBody(fetchMock)).toEqual({ values: { [ATTO]: "-50" }, partial: true });
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer rep");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("הערך צריך להיות בין 0 ל-20,000.");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", alert.id);
    expect(document.body.textContent).not.toContain("must be"); // the English detail
    expect(onAnswered).not.toHaveBeenCalled();
  });

  it("the default button fills the catalog default; a 200 reports the ticket answered", async () => {
    vi.stubGlobal("fetch", respond(200, { ...ticket, status: "answered" }));
    const { onAnswered } = renderDetail();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "השתמש בברירת המחדל ל-ATTO 3" }));
    expect(screen.getByLabelText(ATTO_INPUT)).toHaveValue("300");
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(onAnswered).toHaveBeenCalledWith(ticket.id, false));
  });

  it("nothing filled: says so, sends nothing", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    await userEvent.setup().click(screen.getByRole("button", SEND));
    expect(screen.getByRole("alert")).toHaveTextContent("צריך למלא לפחות שדה אחד.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("a refused token asks for it again", async () => {
    vi.stubGlobal("fetch", respond(401, { detail: "invalid token" }));
    const { onReauth } = renderDetail();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(ATTO_INPUT), "350");
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(onReauth).toHaveBeenCalled());
    expect(screen.getByRole("alert")).toHaveTextContent("טוקן הנציג לא תקף יותר");
  });

  it("the note goes out as answer_text with the values", async () => {
    const fetchMock = respond(200, { ...ticket, status: "answered" });
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(ATTO_INPUT), "350");
    await user.type(screen.getByLabelText(/הערה לעובד\/ת/), "מנובמבר");
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(sentBody(fetchMock)).toEqual({
      values: { [ATTO]: "350" },
      answer_text: "מנובמבר",
      partial: true,
    });
  });
});

/** A car's participation field, as build_ticket_view writes it. */
function car(
  carId: string,
  name: string,
  diff: number,
  extra: Partial<TicketFieldView> = {},
): TicketFieldView {
  return {
    field: `alternative_participation:${carId}`,
    title: "השתתפות עצמית",
    label: "השתתפות בחלופה",
    unit: "ils",
    car_id: carId,
    car_name: name,
    catalog_default: 300,
    options: [],
    facts: [],
    answered: false,
    answer: null,
    comparison: { alternative_title: name, display_diff: diff, pending: true },
    ...extra,
  };
}

const threeCars: TicketWithView = {
  ...ticket,
  blocking_fields: ["CAR-10", "CAR-06", "CAR-11"].map((c) => `alternative_participation:${c}`),
  view: {
    ...ticket.view,
    title: "השתתפות עצמית · 3 רכבים",
    fields: [
      car("CAR-10", "ATTO 3", 611, {
        answered: true,
        answer: 350,
        comparison: { alternative_title: "ATTO 3", display_diff: 611, pending: false },
      }),
      car("CAR-06", "MG4", 1020, { catalog_default: 250 }),
      car("CAR-11", "EV3", 455),
    ],
  },
};

describe("TicketDetail: three cars, one answered", () => {
  it("one section per car: its own heading, default, diff and labelled input", () => {
    renderDetail(threeCars);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("השתתפות עצמית · 3 רכבים");
    const atto = screen.getByRole("region", { name: /ATTO 3/ });
    const mg4 = screen.getByRole("region", { name: /MG4/ });
    const ev3 = screen.getByRole("region", { name: /EV3/ });
    // answered: what the rep sent and the final diff, no input
    expect(within(atto).getByText("נענה:")).toBeInTheDocument();
    expect(within(atto).getByText("+611")).toBeInTheDocument();
    expect(within(atto).queryByRole("textbox")).toBeNull();
    // pending: each car's own numbers, never another car's
    expect(within(mg4).getByText("CAR-06")).toBeInTheDocument();
    expect(within(mg4).getByText("250")).toBeInTheDocument();
    expect(within(mg4).getByText("+1,020")).toBeInTheDocument();
    expect(within(mg4).queryByText("+455")).toBeNull();
    expect(within(ev3).getByText("+455")).toBeInTheDocument();
    expect(within(mg4).getByLabelText("סכום ההשתתפות החודשית ב-MG4 (₪)")).toBeInTheDocument();
    expect(within(ev3).getByLabelText("סכום ההשתתפות החודשית ב-EV3 (₪)")).toBeInTheDocument();
  });

  it("sends only the filled field, as a partial answer; the ticket stays open", async () => {
    const fetchMock = respond(200, { ...threeCars, status: "open" });
    vi.stubGlobal("fetch", fetchMock);
    const { onAnswered } = renderDetail(threeCars);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("סכום ההשתתפות החודשית ב-MG4 (₪)"), "250");
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(onAnswered).toHaveBeenCalledWith(threeCars.id, true));
    expect(sentBody(fetchMock)).toEqual({
      values: { "alternative_participation:CAR-06": "250" },
      partial: true,
    });
  });
});

describe("TicketDetail: the question", () => {
  it("is clamped to three lines, with a 'show more' button when it overflows", async () => {
    const heights = vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockReturnValue(200);
    renderDetail({ ...ticket, question: "שאלה ארוכה מאוד ".repeat(40) });
    const more = screen.getByRole("button", { name: "הצג עוד" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    await userEvent.setup().click(more);
    expect(screen.getByRole("button", { name: "הצג פחות" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    heights.mockRestore();
  });

  it("a short question has no button", () => {
    renderDetail();
    expect(screen.queryByRole("button", { name: "הצג עוד" })).toBeNull();
  });
});

describe("TicketDetail: today's participation and a group approval", () => {
  const today: TicketFieldView = {
    ...car("CAR-09", "COROLLA CROSS 2025", 661),
    field: "current_participation",
    title: "השתתפות עצמית ברכב של היום",
    label: "השתתפות היום",
    comparison: { alternative_title: "ATTO 3", display_diff: 661, pending: true },
  };
  const group: TicketFieldView = {
    field: "group_exception",
    title: "אישור חריג לקבוצה",
    label: "אישור חריג לקבוצה",
    unit: "text",
    car_id: null,
    car_name: null,
    catalog_default: null,
    options: [
      { value: "ג", label: "מאושר לקבוצה ג׳" },
      { value: "not_approved", label: "לא מאושר" },
    ],
    facts: [
      { label: "קבוצה לפי העיסוק", value: "קבוצה ב׳" },
      { label: "הרכב היום", value: "COROLLA CROSS 2025 · קבוצה ג׳" },
    ],
    answered: false,
    answer: null,
    comparison: { alternative_title: "ATTO 3", display_diff: 661, pending: true },
  };
  const withFields = (fields: TicketFieldView[]): TicketWithView => ({
    ...ticket,
    view: { ...ticket.view, title: "x", fields },
  });

  it("today's car with its year, its default, and the diff it affects", () => {
    renderDetail(withFields([today]));
    const section = screen.getByRole("region", { name: /השתתפות עצמית ברכב של היום/ });
    expect(within(section).getAllByText(/COROLLA CROSS 2025/).length).toBeGreaterThan(0);
    expect(within(section).getByText("300")).toBeInTheDocument();
    expect(within(section).getByText(/ההפרש אצל העובד\/ת · ATTO 3/)).toBeInTheDocument();
  });

  it("a car outside the catalog: no default, said in words, no default button", () => {
    const external = { ...today, car_id: null, car_name: "COROLLA CROSS 2023" };
    renderDetail(withFields([{ ...external, catalog_default: null }]));
    expect(screen.getByText("אין ברירת מחדל בקטלוג")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /השתמש בברירת המחדל/ })).toBeNull();
  });

  it("both sections; both values in one answer", async () => {
    const fetchMock = respond(200, { ...ticket, status: "answered" });
    vi.stubGlobal("fetch", fetchMock);
    renderDetail(withFields([today, group]));
    expect(screen.getByRole("region", { name: "אישור חריג לקבוצה" })).toBeInTheDocument();
    expect(screen.getByText("קבוצה ב׳")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("סכום ההשתתפות החודשית ב-COROLLA CROSS 2025 (₪)"), "350");
    await user.click(screen.getByRole("radio", { name: "מאושר לקבוצה ג׳" }));
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(sentBody(fetchMock)).toEqual({
      values: { current_participation: "350", group_exception: "ג" },
      partial: true,
    });
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
