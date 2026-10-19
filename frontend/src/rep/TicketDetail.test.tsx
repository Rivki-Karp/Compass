import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TicketQuestionView, TicketWithView } from "../api/types";
import negative from "../test/fixtures/e001_answer_negative.json";
import inboxFixture from "../test/fixtures/e001_inbox.json";
import questionsInbox from "../test/fixtures/questions_inbox.json";
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

/** The element whose whole text is `text`, across the <bdi> pieces BidiText splits it into. */
const wholeText = (text: string) => (_: string, el: Element | null) =>
  el?.textContent === text && [...el.children].every((child) => child.textContent !== text);

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
    expect(screen.getByText(wholeText(ticket.question))).toHaveClass("line-clamp-3");
    expect(screen.getByText(wholeText("מנהל/ת מוצר · קבוצה ג׳ · היום: COROLLA CROSS"))).toBeInTheDocument();
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
    expect(sentBody(fetchMock)).toEqual({ answers: { [ATTO]: { value: "-50" } }, partial: true });
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
    expect(screen.getByRole("alert")).toHaveTextContent("צריך לענות על שאלה אחת לפחות");
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

  it("a question's note goes out with its value", async () => {
    const fetchMock = respond(200, { ...ticket, status: "answered" });
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(ATTO_INPUT), "350");
    await user.type(screen.getByLabelText(/^הערה/), "מנובמבר");
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(sentBody(fetchMock)).toEqual({
      answers: { [ATTO]: { value: "350", note: "מנובמבר" } },
      partial: true,
    });
  });

  it("needs checking: sent without a value, the input disabled", async () => {
    const fetchMock = respond(200, { ...ticket, status: "open" });
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    const user = userEvent.setup();
    await user.click(screen.getByRole("checkbox", { name: "לא ידוע לי / צריך לבדוק" }));
    expect(screen.getByLabelText(ATTO_INPUT)).toBeDisabled();
    await user.type(screen.getByLabelText(/^הערה/), "בודק מול השכר");
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(sentBody(fetchMock)).toEqual({
      answers: { [ATTO]: { status: "needs_checking", note: "בודק מול השכר" } },
      partial: true,
    });
  });
});

/** A car's participation question, as build_ticket_view writes it. */
function car(
  carId: string,
  name: string,
  diff: number,
  extra: Partial<TicketQuestionView> = {},
): TicketQuestionView {
  const field = `alternative_participation:${carId}`;
  return {
    id: field,
    kind: "bound",
    bound_field: field,
    type: "amount",
    title: "השתתפות עצמית",
    prompt_he: "",
    label: `סכום ההשתתפות החודשית ב-${name} (₪)`,
    car_id: carId,
    car_name: name,
    catalog_default: 300,
    options: [],
    search_options: [],
    facts: [],
    status: "pending",
    answer: null,
    note: null,
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
    questions: [
      car("CAR-10", "ATTO 3", 611, {
        status: "answered",
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
      answers: { "alternative_participation:CAR-06": { value: "250" } },
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
  const today: TicketQuestionView = {
    ...car("CAR-09", "COROLLA CROSS 2025", 661),
    id: "current_participation",
    bound_field: "current_participation",
    title: "השתתפות עצמית ברכב של היום",
    comparison: { alternative_title: "ATTO 3", display_diff: 661, pending: true },
  };
  const group: TicketQuestionView = {
    id: "group_exception",
    kind: "bound",
    bound_field: "group_exception",
    type: "choice",
    title: "אישור חריג לקבוצה",
    prompt_he: "",
    label: "אישור חריג לקבוצה",
    car_id: null,
    car_name: null,
    catalog_default: null,
    options: [
      { value: "ג", label: "מאושר לקבוצה ג׳", detail: null },
      { value: "not_approved", label: "לא מאושר", detail: null },
    ],
    search_options: [],
    facts: [
      { label: "קבוצה לפי העיסוק", value: "קבוצה ב׳" },
      { label: "הרכב היום", value: "COROLLA CROSS 2025 · קבוצה ג׳" },
    ],
    status: "pending",
    answer: null,
    note: null,
    comparison: { alternative_title: "ATTO 3", display_diff: 661, pending: true },
  };
  const withFields = (questions: TicketQuestionView[]): TicketWithView => ({
    ...ticket,
    view: { ...ticket.view, title: "x", questions },
  });

  it("today's car with its year, its default, and the diff it affects", () => {
    renderDetail(withFields([today]));
    const section = screen.getByRole("region", { name: /השתתפות עצמית ברכב של היום/ });
    expect(within(section).getAllByText(/COROLLA CROSS 2025/).length).toBeGreaterThan(0);
    expect(within(section).getByText("300")).toBeInTheDocument();
    expect(within(section).getByText(wholeText("ההפרש אצל העובד/ת · ATTO 3"))).toBeInTheDocument();
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
    const groupSection = screen.getByRole("region", { name: "אישור חריג לקבוצה" });
    expect(within(groupSection).getByText("קבוצה ב׳")).toBeInTheDocument();
    // a group question shows its facts only: no car default or diff tiles
    expect(within(groupSection).queryByText("ברירת מחדל מהקטלוג")).toBeNull();
    expect(within(groupSection).queryByText(/ההפרש אצל העובד/)).toBeNull();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("סכום ההשתתפות החודשית ב-COROLLA CROSS 2025 (₪)"), "350");
    await user.click(screen.getByRole("radio", { name: "מאושר לקבוצה ג׳" }));
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(sentBody(fetchMock)).toEqual({
      answers: { current_participation: { value: "350" }, group_exception: { value: "ג" } },
      partial: true,
    });
  });
});

describe("TicketDetail: an occupation question and a free question (recorded)", () => {
  const recorded = must((questionsInbox as unknown as TicketWithView[])[0]);
  const OCCUPATION = /סיווג עיסוק/;
  const PARKING = /חניה לעובדים/;

  it("the title and one section per question; no group question", () => {
    renderDetail(recorded);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "סיווג עיסוק · מפתח AI + האם יש חניה לעובדים בבניין המשרדים?",
    );
    expect(screen.getAllByRole("region")).toHaveLength(2);
    expect(screen.queryByText(/אישור חריג לקבוצה/)).toBeNull();
  });

  it("the occupation is a picker of the table's closest titles with their group", () => {
    renderDetail(recorded);
    const section = screen.getByRole("region", { name: OCCUPATION });
    expect(
      within(section).getByRole("radio", { name: "מפתח/ת תוכנה · קבוצה ב׳" }),
    ).toBeInTheDocument();
    expect(
      within(section).getByRole("radio", { name: "עיסוק אחר (לפרט בהערה)" }),
    ).toBeInTheDocument();
    // no free-text box for the occupation: the only text boxes are the search and the note
    expect(within(section).getAllByRole("textbox").map((e) => e.id)).toEqual(["answer-0-note"]);
    // the tiles: what the employee wrote, the group the choice gives; no car tiles
    expect(within(section).getByText(wholeText("מפתח AI"))).toBeInTheDocument();
    expect(within(section).queryByText("ברירת מחדל מהקטלוג")).toBeNull();
    expect(within(section).queryByText(/ההפרש אצל העובד/)).toBeNull();
  });

  it("choosing a title shows its group; the search finds any title in the table", async () => {
    const fetchMock = respond(200, { ...recorded, status: "open" });
    vi.stubGlobal("fetch", fetchMock);
    renderDetail(recorded);
    const section = screen.getByRole("region", { name: OCCUPATION });
    const user = userEvent.setup();
    await user.type(within(section).getByRole("searchbox"), "מחלקה");
    await user.click(within(section).getByRole("radio", { name: "מנהל/ת מחלקה · קבוצה ד׳" }));
    expect(within(section).getByText("קבוצה ד׳")).toBeInTheDocument(); // the group tile
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(sentBody(fetchMock)).toEqual({
      answers: { q1: { value: "מנהל/ת מחלקה" } },
      partial: true,
    });
  });

  it("'another occupation' asks for the note", async () => {
    renderDetail(recorded);
    const section = screen.getByRole("region", { name: OCCUPATION });
    await userEvent.setup().click(within(section).getByRole("radio", { name: /עיסוק אחר/ }));
    expect(within(section).getByLabelText("הערה (חובה: מה העיסוק)")).toBeRequired();
  });

  it("the free yes/no question: yes and no, no tiles; its answer and note go by id", async () => {
    const fetchMock = respond(200, { ...recorded, status: "open" });
    vi.stubGlobal("fetch", fetchMock);
    renderDetail(recorded);
    const section = screen.getByRole("region", { name: PARKING });
    expect(within(section).getAllByRole("radio").map((r) => r.getAttribute("value"))).toEqual([
      "yes",
      "no",
    ]);
    expect(within(section).queryByText(/ההפרש אצל העובד|ברירת מחדל/)).toBeNull();
    const user = userEvent.setup();
    await user.click(within(section).getByRole("radio", { name: "כן" }));
    await user.type(within(section).getByLabelText(/^הערה/), "בחניון התת-קרקעי");
    await user.click(screen.getByRole("button", SEND));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(sentBody(fetchMock)).toEqual({
      answers: { q2: { value: "yes", note: "בחניון התת-קרקעי" } },
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
