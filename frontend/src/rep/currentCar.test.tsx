/** A current_car question (fix/current-car): a picker over the catalog, from a recorded inbox. The
 * employee wrote "מאזדה"; the server lists the cars it may mean, a search over the whole
 * catalog, and "not in the catalog", which needs a note. */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TicketWithView } from "../api/types";
import inbox from "../test/fixtures/current_car_inbox.json";
import { must } from "../test/views";
import { TicketDetail } from "./TicketDetail";

const ticket = must((inbox as unknown as TicketWithView[])[0]);
const MAZDA = "MAZDA 3 2025 · בנזין · קבוצה ג׳";
const NOT_IN_CATALOG = "הרכב לא בקטלוג (לפרט בהערה)";

function renderDetail() {
  render(<TicketDetail ticket={ticket} token="rep" onAnswered={vi.fn()} onReauth={vi.fn()} />);
  return screen.getByRole("region", { name: /הרכב של היום/ });
}

afterEach(() => vi.unstubAllGlobals());

describe("TicketDetail: today's car", () => {
  it("the closest catalog cars, what the employee wrote, and the choice's drive and group", async () => {
    const section = renderDetail();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("הרכב של היום · מאזדה");
    expect(within(section).getByText("מאזדה")).toBeInTheDocument(); // איך העובד/ת תיאר/ה
    const radios = within(section).getAllByRole("radio").map((r) => r.getAttribute("value"));
    expect(radios).toEqual(["CAR-13", "other"]); // "not in the catalog" last
    await userEvent.setup().click(within(section).getByRole("radio", { name: MAZDA }));
    expect(within(section).getByText("הקבוצה וההנעה לפי הבחירה")).toBeInTheDocument();
    expect(within(section).getByText("בנזין · קבוצה ג׳", { exact: true })).toBeInTheDocument();
  });

  it("the search finds any catalog car, by name or by drive and group, ignoring case", async () => {
    const section = renderDetail();
    const user = userEvent.setup();
    const search = within(section).getByRole("searchbox", { name: "לא ברשימה? חיפוש בקטלוג המלא" });
    await user.type(search, "corolla");
    expect(within(section).getByRole("radio", { name: "COROLLA 2026 · בנזין · קבוצה ב׳" })).toBeInTheDocument();
    await user.clear(search);
    await user.type(search, "zzz");
    expect(within(section).getByText("אין רכב כזה בקטלוג.")).toBeInTheDocument();
  });

  it("'not in the catalog' asks for the note; the answer sends the car's id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...ticket, status: "answered" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const section = renderDetail();
    const user = userEvent.setup();
    await user.click(within(section).getByRole("radio", { name: NOT_IN_CATALOG }));
    expect(within(section).getByLabelText("הערה (חובה: איזה רכב, ושנת הרישום אם ידועה)")).toBeRequired();
    await user.click(within(section).getByRole("radio", { name: MAZDA }));
    expect(within(section).getByLabelText(/^הערה/)).not.toBeRequired();
    await user.click(screen.getByRole("button", { name: "אישור ושליחה לעובד/ת" }));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({ answers: { q1: { value: "CAR-13" } } });
  });
});
