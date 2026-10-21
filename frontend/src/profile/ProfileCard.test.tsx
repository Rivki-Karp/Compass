import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ProfileOffer } from "../api/types";
import { initialSession, reduce } from "../state/session";
import type { SessionEvent } from "../api/types";
import { originText } from "../lib/numberSources";
import { ProfileCard } from "./ProfileCard";

const field = (name: string, label: string, value: string, unit: "ils" | "percent" | "text") => ({
  name,
  label,
  value,
  display: value,
  unit,
  source: "employee" as const,
  source_chip: "employee_input" as const,
  source_label: "לפי דבריך",
  saved_at: "2026-10-20T10:00:00+00:00",
  age_days: 1,
});
const OFFER: ProfileOffer = {
  fields: [
    field("occupation", "עיסוק", "מפתחת תוכנה", "text"),
    field("base_salary", "שכר בסיס", "18500", "ils"),
    field("pension_percent", "הפרשת עובד לפנסיה", "6.5", "percent"),
  ],
  saved_at: "2026-10-20T10:00:00+00:00",
  age_days: 1,
  stale: false,
  stale_note: null,
};

function show(over: Partial<ProfileOffer> = {}, busy = false, error: string | null = null) {
  const calls = { apply: vi.fn(), dismiss: vi.fn(), del: vi.fn() };
  render(
    <ProfileCard
      offer={{ ...OFFER, ...over }}
      busy={busy}
      error={error}
      onApply={calls.apply}
      onDismiss={calls.dismiss}
      onDelete={calls.del}
    />,
  );
  return calls;
}

describe("the saved-details card", () => {
  it("shows each detail with its source chip, and uses nothing until a button is pressed", () => {
    const calls = show();
    expect(screen.getByRole("heading")).toHaveTextContent(/יש לי פרטים מהשיחה מ־\d\d\/\d\d/);
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("שכר בסיס");
    expect(rows[1]).toHaveTextContent("18,500");
    expect(rows[1]).toHaveTextContent("לפי דבריך");
    expect(rows[2]).toHaveTextContent("6.5%");
    expect(calls.apply).not.toHaveBeenCalled();
  });

  it("'להשתמש בהם' keeps everything that is shown", async () => {
    const calls = show();
    await userEvent.click(screen.getByRole("button", { name: "להשתמש בהם" }));
    expect(calls.apply).toHaveBeenCalledWith([
      { name: "occupation", action: "keep" },
      { name: "base_salary", action: "keep" },
      { name: "pension_percent", action: "keep" },
    ]);
  });

  it("a removed row is dropped, and can be brought back", async () => {
    const calls = show();
    await userEvent.click(screen.getByRole("button", { name: "הסרת שכר בסיס" }));
    expect(screen.getByText("לא ישמש בשיחה")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "להשתמש בהם" }));
    expect(calls.apply.mock.calls[0]?.[0]).toContainEqual({ name: "base_salary", action: "drop" });
    await userEvent.click(screen.getByRole("button", { name: "החזרת שכר בסיס" }));
    await userEvent.click(screen.getByRole("button", { name: "להשתמש בהם" }));
    expect(calls.apply.mock.calls[1]?.[0]).toContainEqual({ name: "base_salary", action: "keep" });
  });

  it("'לעדכן' lets numbers be typed over; only a changed one is an edit", async () => {
    const calls = show();
    await userEvent.click(screen.getByRole("button", { name: "לעדכן" }));
    expect(screen.queryByRole("button", { name: "להשתמש בהם" })).toBeNull();
    const salary = screen.getByLabelText("שכר בסיס");
    await userEvent.clear(salary);
    await userEvent.type(salary, "19000");
    expect(screen.queryByLabelText("עיסוק")).toBeNull(); // the occupation is kept or removed
    await userEvent.click(screen.getByRole("button", { name: "אישור ושמירה" }));
    expect(calls.apply).toHaveBeenCalledWith([
      { name: "occupation", action: "keep" },
      { name: "base_salary", action: "edit", value: "19000" },
      { name: "pension_percent", action: "keep" },
    ]);
  });

  it("'להתחיל מחדש' dismisses; the delete link asks first", async () => {
    const calls = show();
    await userEvent.click(screen.getByRole("button", { name: "להתחיל מחדש" }));
    expect(calls.dismiss).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: "מחיקת הפרטים השמורים" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("למחוק את הפרטים השמורים?");
    await userEvent.click(screen.getByRole("button", { name: "ביטול" }));
    expect(calls.del).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "מחיקת הפרטים השמורים" }));
    await userEvent.click(screen.getByRole("button", { name: "מחיקה" }));
    expect(calls.del).toHaveBeenCalledOnce();
  });

  it("an old profile says the details may have changed; an error is announced; busy disables", () => {
    show({ stale: true, stale_note: "ייתכן שהפרטים השתנו" }, true, "לא הצלחנו");
    expect(screen.getByText("ייתכן שהפרטים השתנו")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("לא הצלחנו");
    expect(screen.getByRole("button", { name: "להשתמש בהם" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "להתחיל מחדש" })).toBeDisabled();
  });
});

describe("the offer in the session state", () => {
  const ev = (seq: number, type: string, payload: unknown) =>
    ({ session_id: "s", seq, type, payload, created_at: "t" }) as SessionEvent;

  it("is pending after the offer and gone once it is applied or dismissed", () => {
    const offered = reduce(initialSession, ev(2, "profile_offer", OFFER));
    expect(offered.profile?.offer.fields).toHaveLength(3);
    const applied = reduce(offered, ev(3, "profile_applied", { values: {} }));
    expect(applied.profile).toBeNull();
    const dismissed = reduce(offered, ev(3, "profile_dismissed", { offer_seq: 2 }));
    expect(dismissed.profile).toBeNull();
  });
});

describe("the date of a previous value", () => {
  it("fills {date} as DD/MM, or leaves the clause out without one", () => {
    expect(originText("משיחה קודמת, {date}", "2026-10-20T10:00:00+00:00")).toMatch(
      /^משיחה קודמת, \d\d\/\d\d$/,
    );
    expect(originText("משיחה קודמת, {date}", null)).toBe("משיחה קודמת");
  });
});
