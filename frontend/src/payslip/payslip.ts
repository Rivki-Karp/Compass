/**
 * The payslip confirmation card's logic, pure (tested on its own). The server reads the
 * payslip into a pending candidate; the employee checks each field, edits or removes it, and
 * confirms. What is sent is only what the employee kept; the server decides the source (the
 * candidate's value: "לפי התלוש"; an edited one: the employee's).
 */

import type { PayslipCandidateField } from "../api/types";

export type Unit = "ils" | "percent" | "points" | "month";

/** The card's fields, in order. `info`: shown, never a profile value. */
export const FIELDS: { name: string; label: string; unit: Unit; info?: true }[] = [
  { name: "base_salary", label: "שכר יסוד", unit: "ils" },
  { name: "commissions", label: "עמלות", unit: "ils" },
  { name: "bonus", label: "בונוס", unit: "ils" },
  { name: "pension_percent", label: "הפרשת עובד לפנסיה", unit: "percent" },
  { name: "study_fund_percent", label: "הפרשת עובד לקרן השתלמות", unit: "percent" },
  { name: "credit_points", label: "נקודות זיכוי", unit: "points" },
  { name: "car_benefit_value", label: "שווי שימוש ברכב", unit: "ils", info: true },
  { name: "payslip_month", label: "חודש התלוש", unit: "month", info: true },
];

/** Sent to the server when confirmed (payslip_month never is: it is information only). */
const SENT = new Set(FIELDS.filter((f) => f.unit !== "month").map((f) => f.name));

export interface Row {
  name: string;
  label: string;
  unit: Unit;
  info: boolean;
  /** What the payslip says (null: unknown, or not read clearly). */
  read: string | null;
  confidence: PayslipCandidateField["confidence"];
  flag: PayslipCandidateField["flag"];
  /** What the employee has in the field now. */
  value: string;
  removed: boolean;
}

export function rows(fields: Record<string, PayslipCandidateField>): Row[] {
  return FIELDS.filter((f) => f.name in fields).map((f) => {
    const field = fields[f.name] as PayslipCandidateField;
    return {
      name: f.name,
      label: f.label,
      unit: f.unit,
      info: f.info === true,
      read: field.value,
      confidence: field.confidence,
      flag: field.flag,
      value: field.value ?? "",
      // a field the payslip does not show starts out of the card's answer, never as 0
      removed: field.value === null && field.flag === null,
    };
  });
}

/** The warning a row shows, if any. */
export function warning(row: Row): string | null {
  if (row.flag) return "לא נקרא בבירור מהתלוש. הזינו את הערך או הסירו את השדה.";
  if (row.read === null) return "לא מופיע בתלוש.";
  if (row.confidence === "low") return "ודאות נמוכה. בדקו שהערך נכון.";
  return null;
}

const NUMBER = /^\d{1,7}(\.\d{1,2})?$/;

/** The value as the server takes it (thousands separators dropped), or null when it is not a
 * plain number. */
export function plain(value: string): string | null {
  const text = value.replace(/[,\s₪%]/g, "");
  return NUMBER.test(text) ? text : null;
}

/** Whether every kept row has a number in it (the button is enabled only then). */
export function ready(list: Row[]): boolean {
  return list.every((r) => r.removed || !SENT.has(r.name) || plain(r.value) !== null);
}

/** The POST /payslip/confirm body: the kept rows' values. A removed row is rejected. */
export function confirmBody(list: Row[]): { fields: Record<string, string> } {
  const fields: Record<string, string> = {};
  for (const row of list) {
    if (row.removed || !SENT.has(row.name)) continue;
    const value = plain(row.value);
    if (value !== null) fields[row.name] = value;
  }
  return { fields };
}

/** The client's quick checks before a file is sent: type and size only (the server's checks
 * are the real ones). The message, or null. */
export function precheck(file: { type: string; size: number }, limits: PayslipLimits): string | null {
  if (!limits.types.includes(file.type)) return "אפשר להעלות רק PDF, JPG או PNG.";
  if (file.size === 0) return "לא התקבל קובץ.";
  if (file.size > limits.max_bytes) {
    return `הקובץ גדול מדי. אפשר עד ${Math.max(1, Math.round(limits.max_bytes / 2 ** 20))}MB.`;
  }
  return null;
}

export interface PayslipLimits {
  max_bytes: number;
  max_pages: number;
  types: string[];
}

export const PRIVACY_NOTICE =
  "התלוש נשלח לעיבוד אצל Anthropic, רק לחילוץ נתוני השכר, ואינו נשמר אצלנו. אל תעלו מסמך אחר.";
