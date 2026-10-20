import { render, renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PayslipCandidateField, SessionEvent } from "../api/types";
import { initialSession, reduce } from "../state/session";
import { must } from "../test/views";
import { confirmBody, plain, precheck, ready, rows, warning } from "./payslip";
import { PayslipCard } from "./PayslipCard";
import { usePayslip } from "./usePayslip";

const field = (
  value: string | null,
  confidence: PayslipCandidateField["confidence"] = "high",
  flag: PayslipCandidateField["flag"] = null,
): PayslipCandidateField => ({ value, confidence, flag });

const FIELDS = {
  base_salary: field("18500"),
  bonus: field("0", "medium"),
  pension_percent: field(null, "high", "out_of_range"),
  credit_points: field("2.25", "low"),
  commissions: field(null, "low"),
  payslip_month: field("2026-09"),
};
const LIMITS = { max_bytes: 5 * 2 ** 20, max_pages: 3, types: ["application/pdf", "image/jpeg", "image/png"] };

describe("the card's logic", () => {
  it("rows in the card's order; a field the payslip does not show starts removed", () => {
    const list = rows(FIELDS);
    expect(list.map((r) => r.name)).toEqual([
      "base_salary",
      "commissions",
      "bonus",
      "pension_percent",
      "credit_points",
      "payslip_month",
    ]);
    expect(list.find((r) => r.name === "commissions")?.removed).toBe(true); // never a 0
    expect(list.find((r) => r.name === "pension_percent")?.removed).toBe(false); // flagged: shown
  });

  it("warnings: flagged, missing, low confidence, none", () => {
    const byName = Object.fromEntries(rows(FIELDS).map((r) => [r.name, r]));
    expect(warning(must(byName.pension_percent))).toContain("לא נקרא בבירור");
    expect(warning(must(byName.commissions))).toBe("לא מופיע בתלוש.");
    expect(warning(must(byName.credit_points))).toContain("ודאות נמוכה");
    expect(warning(must(byName.base_salary))).toBeNull();
  });

  it("the body: kept rows only, thousands separators dropped, the month never sent", () => {
    const list = rows(FIELDS).map((r) =>
      r.name === "base_salary"
        ? { ...r, value: "18,750" }
        : r.name === "pension_percent"
          ? { ...r, removed: true }
          : r,
    );
    expect(confirmBody(list)).toEqual({
      fields: { base_salary: "18750", bonus: "0", credit_points: "2.25" },
    });
  });

  it("ready only when every kept field has a plain number", () => {
    const list = rows(FIELDS);
    expect(ready(list)).toBe(false); // the flagged pension is kept and empty
    expect(ready(list.map((r) => (r.name === "pension_percent" ? { ...r, value: "6" } : r)))).toBe(
      true,
    );
    expect(plain("₪ 18,500")).toBe("18500");
    expect(plain("abc")).toBeNull();
    expect(plain("1.234")).toBeNull();
  });

  it("the client's quick checks: type and size only", () => {
    expect(precheck({ type: "application/pdf", size: 1000 }, LIMITS)).toBeNull();
    expect(precheck({ type: "image/gif", size: 1000 }, LIMITS)).toBe("אפשר להעלות רק PDF, JPG או PNG.");
    expect(precheck({ type: "image/png", size: 6 * 2 ** 20 }, LIMITS)).toContain("5MB");
    expect(precheck({ type: "image/png", size: 0 }, LIMITS)).toBe("לא התקבל קובץ.");
  });
});

describe("PayslipCard", () => {
  it("edits, removes, restores and confirms with one button; numbers in <bdi>", async () => {
    const onConfirm = vi.fn();
    render(<PayslipCard pending={{ seq: 7, fields: FIELDS }} busy={false} onConfirm={onConfirm} />);
    const card = screen.getByRole("region", { name: "מה קראנו מהתלוש" });
    expect(within(card).getAllByRole("button", { name: "אישור ושמירה" })).toHaveLength(1);
    const confirm = within(card).getByRole("button", { name: "אישור ושמירה" });
    expect(confirm).toBeDisabled(); // the flagged pension needs a value or removal

    await userEvent.click(within(card).getByRole("button", { name: "הסרת הפרשת עובד לפנסיה" }));
    expect(confirm).toBeEnabled();
    const salary = within(card).getByLabelText("שכר יסוד");
    await userEvent.clear(salary);
    await userEvent.type(salary, "19000");
    await userEvent.click(within(card).getByRole("button", { name: "הסרת בונוס" }));
    expect(within(card).getByText("0").tagName).toBe("BDI"); // the removed value, isolated
    await userEvent.click(must(within(card).getAllByRole("button", { name: "החזרה" })[1]));
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith({ base_salary: "19000", bonus: "0", credit_points: "2.25" });
  });

  it("shows the low-confidence warning, tied to its field", () => {
    render(<PayslipCard pending={{ seq: 7, fields: FIELDS }} busy={false} onConfirm={() => {}} />);
    const points = screen.getByLabelText("נקודות זיכוי");
    expect(points.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText("ודאות נמוכה. בדקו שהערך נכון.")).toBeInTheDocument();
  });
});

describe("the session's pending payslip", () => {
  const base = { session_id: "s", created_at: "2026-10-20T12:00:00Z" };
  it("set by payslip_extracted, cleared by payslip_confirmed (a reload replays both)", () => {
    const events = [
      { ...base, seq: 1, type: "payslip_extracted", payload: { fields: FIELDS, dropped_keys: 0 } },
    ] as SessionEvent[];
    const read = events.reduce(reduce, initialSession);
    expect(read.payslip).toEqual({ seq: 1, fields: FIELDS });
    const confirmed = reduce(read, {
      ...base,
      seq: 2,
      type: "payslip_confirmed",
      payload: { candidate_seq: 1, applied: {}, kept_representative: [], waiting_for_rep: [], car_hint: null },
    } as SessionEvent);
    expect(confirmed.payslip).toBeNull();
  });
});

describe("usePayslip", () => {
  it("nothing at all when the server does not report the flag", () => {
    const { result } = renderHook(() =>
      usePayslip({ sessionId: "s", limits: undefined, pending: null }),
    );
    expect(result.current).toEqual({ attach: null, tray: null });
  });

  it("the attach button asks for the privacy notice first, once per session", async () => {
    sessionStorage.clear();
    function Harness() {
      const { attach, tray } = usePayslip({ sessionId: "s1", limits: LIMITS, pending: null });
      return (
        <div>
          {tray}
          {attach}
        </div>
      );
    }
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "צירוף תלוש שכר" }));
    const notice = screen.getByRole("dialog", { name: "לפני שמעלים תלוש" });
    expect(notice).toHaveTextContent("אצל Anthropic");
    await userEvent.click(within(notice).getByRole("button", { name: "הבנתי, לבחירת קובץ" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "צירוף תלוש שכר" }));
    expect(screen.queryByRole("dialog")).toBeNull(); // acknowledged for this session
  });
});
