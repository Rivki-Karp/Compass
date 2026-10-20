import type { ChipSource } from "../api/types";

/** Where an input value came from (brief §3.2). Pending is visually distinct: dashed amber
 * border, clock icon. Labels are the design's fixed vocabulary for the sources. */
export const CHIP: Record<ChipSource, { label: string; className: string }> = {
  employee_input: {
    label: "לפי דבריך",
    className: "text-chip-employee bg-chip-employee-bg border-transparent",
  },
  occupation: {
    label: "לפי העיסוק",
    className: "text-chip-occupation bg-chip-occupation-bg border-transparent",
  },
  representative: {
    label: "אושר על ידי נציג",
    className: "text-chip-rep bg-chip-rep-bg border-transparent font-semibold",
  },
  catalog_default: {
    label: "ברירת מחדל מהקטלוג",
    className: "text-chip-catalog bg-chip-catalog-bg border-chip-catalog-border",
  },
  payslip: {
    label: "לפי התלוש",
    className: "text-chip-payslip bg-chip-payslip-bg border-transparent",
  },
  pending_rep: {
    label: "ממתינה לנציג",
    className: "text-chip-pending bg-chip-pending-bg border-chip-pending-border border-dashed",
  },
};
