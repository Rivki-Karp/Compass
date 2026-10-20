/**
 * The payslip confirmation card's logic, pure (tested on its own). The server reads the
 * payslip into a pending candidate; the employee checks each field, edits or removes it, and
 * confirms. What is sent is only what the employee kept; the server decides the source (the
 * candidate's value: "לפי התלוש"; an edited one: the employee's).
 *
 * Israeli payslips usually print the pension and study fund deduction AMOUNTS with the wage they
 * are calculated on, not a percent. The server derives the percent (amount / wage * 100, exact)
 * and sends it as `<field>_derived` with its basis; the card shows it with where it came from,
 * and when the payslip also prints a different percent, shows both and lets the employee pick.
 */

import type { PayslipCandidateField } from "../api/types";

export type Unit = "ils" | "percent" | "points" | "month";

/** The card's fields, in order. `info`: shown, never a profile value. `noneable`: when the
 * payslip has no such line, one tap on "אין" answers 0 (the employee's own answer). */
export const FIELDS: { name: string; label: string; unit: Unit; info?: true; noneable?: true }[] = [
  { name: "base_salary", label: "שכר יסוד", unit: "ils" },
  { name: "commissions", label: "עמלות", unit: "ils", noneable: true },
  { name: "bonus", label: "בונוס", unit: "ils", noneable: true },
  { name: "pension_percent", label: "הפרשת עובד לפנסיה", unit: "percent" },
  { name: "study_fund_percent", label: "הפרשת עובד לקרן השתלמות", unit: "percent" },
  { name: "credit_points", label: "נקודות זיכוי", unit: "points" },
  { name: "car_benefit_value", label: "שווי שימוש ברכב", unit: "ils", info: true },
  { name: "payslip_month", label: "חודש התלוש", unit: "month", info: true },
];

/** Sent to the server when confirmed (payslip_month never is: it is information only). */
const SENT = new Set(FIELDS.filter((f) => f.unit !== "month").map((f) => f.name));

/** A percent the server derived from the printed deduction amount and its wage. */
export interface Derived {
  value: string | null;
  confidence: PayslipCandidateField["confidence"];
  amount: string;
  wage: string;
  flag: PayslipCandidateField["flag"];
}

export interface Choice {
  value: string;
  label: string;
}

export interface Row {
  name: string;
  label: string;
  unit: Unit;
  info: boolean;
  /** One tap on "אין" answers 0 (commissions, bonus the payslip does not show). */
  noneable: boolean;
  /** The percent the server computed from the printed amount and wage, if it did. */
  derived: Derived | null;
  /** A printed percent and a derived one that differ: both are offered, the employee picks. */
  choices: Choice[] | null;
  /** A deduction amount was printed without the wage it is calculated on: nothing derived. */
  hint: string | null;
  /** What the payslip says (null: unknown, or not read clearly). */
  read: string | null;
  confidence: PayslipCandidateField["confidence"];
  flag: PayslipCandidateField["flag"];
  /** What the employee has in the field now. */
  value: string;
  removed: boolean;
}

/** 20000 -> "20,000"; 1234.5 -> "1,234.5" (a Decimal text, never rounded). */
export function grouped(text: string): string {
  const [whole = "", fraction] = text.split(".");
  const digits = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return fraction === undefined ? digits : `${digits}.${fraction}`;
}

/** "חושב מהתלוש: 1,200 מתוך 20,000" */
export function basisText(derived: Pick<Derived, "amount" | "wage">): string {
  return `חושב מהתלוש: ${grouped(derived.amount)} מתוך ${grouped(derived.wage)}`;
}

/** The fields behind a percent field. */
const BEHIND: Record<string, { derived: string; amount: string; wage: string }> = {
  pension_percent: {
    derived: "pension_percent_derived",
    amount: "employee_pension_amount",
    wage: "pension_wage",
  },
  study_fund_percent: {
    derived: "study_fund_percent_derived",
    amount: "employee_study_fund_amount",
    wage: "study_fund_wage",
  },
};

const NOT_SHOWN: PayslipCandidateField = { value: null, confidence: "low", flag: null };

function derivedOf(fields: Record<string, PayslipCandidateField>, name: string): Derived | null {
  const behind = BEHIND[name];
  const field = behind ? fields[behind.derived] : undefined;
  if (!field?.basis) return null;
  return {
    value: field.value,
    confidence: field.confidence,
    amount: field.basis.amount,
    wage: field.basis.wage,
    flag: field.flag,
  };
}

export function rows(fields: Record<string, PayslipCandidateField>): Row[] {
  const derivedKey = (name: string) => BEHIND[name]?.derived ?? "";
  return FIELDS.filter((f) => f.name in fields || derivedKey(f.name) in fields).map((f) => {
    const printed = fields[f.name] ?? NOT_SHOWN;
    const derived = derivedOf(fields, f.name);
    const behind = BEHIND[f.name];
    const amount = behind ? fields[behind.amount]?.value : null;
    const wage = behind ? fields[behind.wage]?.value : null;
    // a printed percent and a derived one that differ: both are shown, the employee picks
    const both =
      printed.value !== null &&
      derived?.value != null &&
      Number(printed.value) !== Number(derived.value);
    const read = printed.value ?? derived?.value ?? null;
    const usedDerived = printed.value === null && derived?.value != null;
    const flag = read === null ? (printed.flag ?? derived?.flag ?? null) : null;
    const choices: Choice[] | null =
      both && derived
        ? [
            { value: printed.value as string, label: `${printed.value}% (מודפס בתלוש)` },
            { value: derived.value as string, label: `${derived.value}% (${basisText(derived)})` },
          ]
        : null;
    return {
      name: f.name,
      label: f.label,
      unit: f.unit,
      info: f.info === true,
      noneable: f.noneable === true,
      derived,
      choices,
      hint:
        amount && !wage && !derived
          ? `נמצא ניכוי של ${grouped(amount)} ₪ אך לא השכר שעליו הוא מחושב, ולכן לא חושב אחוז.`
          : null,
      read,
      confidence: usedDerived && derived ? derived.confidence : printed.confidence,
      flag,
      value: both ? "" : (read ?? ""),
      // a field the payslip does not show starts out of the card's answer, never as 0; a
      // percent with two different readings waits for the employee's pick
      removed: !both && read === null && flag === null,
    };
  });
}

/** The warning a row shows, if any. */
export function warning(row: Row): string | null {
  if (row.choices) return "בתלוש מופיעים שני ערכים שונים. בחרו את הנכון.";
  if (row.flag && row.derived && row.derived.value === null && row.read === null) {
    return `${basisText(row.derived)}, אך התוצאה אינה אחוז תקין. הזינו את האחוז או הסירו את השדה.`;
  }
  if (row.flag) return "לא נקרא בבירור מהתלוש. הזינו את הערך או הסירו את השדה.";
  if (row.read === null) return row.hint ?? "לא מופיע בתלוש.";
  if (row.confidence === "low") return "ודאות נמוכה. בדקו שהערך נכון.";
  return null;
}

/** The caption under a derived percent while the field still holds it (an edit hides it). */
export function basisCaption(row: Row): string | null {
  if (!row.derived || row.derived.value === null) return null;
  return plain(row.value) === row.derived.value ? `(${basisText(row.derived)})` : null;
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
