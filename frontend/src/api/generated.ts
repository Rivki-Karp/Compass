// Generated from the Pydantic models by `uv run python tasks.py ts-types`. Do not edit.
// Source: compass/tools/view.py (views), compass/state/store.py (event types).

export const EVENT_TYPES = [
  "agent_error",
  "agent_finished",
  "agent_started",
  "assistant_message",
  "comparison_ready",
  "comparison_set_ready",
  "current_situation_set",
  "guard_check",
  "payslip_confirmed",
  "payslip_extracted",
  "payslip_failed",
  "profile_updated",
  "session_created",
  "session_status",
  "ticket_answered",
  "ticket_opened",
  "tool_call",
  "tool_result",
  "user_message",
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

export interface ComparisonView {
  version: number;
  today_title: string;
  alternative_title: string;
  alternative_kind: string;
  alternative_car_id: string | null;
  alternative_details: string | null;
  group: string | null;
  group_label: string | null;
  group_budget: number | null;
  today_net: number | null;
  alternative_net: number | null;
  display_diff: number | null;
  direction: "up" | "down" | "flat" | "unknown";
  diff_note: string | null;
  breakdown: ViewLine[];
  inputs: ViewInput[];
  pending: boolean;
  pending_fields: string[];
  partial: boolean;
  missing: ViewField[];
  warnings: ViewWarning[];
  hypothetical: boolean;
  rules_version: string;
  computed_by: ViewComputedBy;
}

export interface TicketComparisonView {
  alternative_title: string;
  display_diff: number | null;
  pending: boolean;
  diff_note: string | null;
}

export interface TicketFactView {
  label: string;
  value: string;
}

export interface TicketFieldView {
  field: string;
  title: string;
  label: string;
  unit: "ils" | "percent" | "points" | "count" | "text";
  car_id: string | null;
  car_name: string | null;
  catalog_default: number | null;
  options: TicketOptionView[];
  facts: TicketFactView[];
  answered: boolean;
  answer: number | string | null;
  comparison: TicketComparisonView | null;
}

export interface TicketOptionView {
  value: string;
  label: string;
  detail: string | null;
}

export interface TicketQuestionView {
  id: string;
  kind: "bound" | "free";
  bound_field: string | null;
  type: "amount" | "choice" | "yes_no" | "text";
  title: string;
  prompt_he: string;
  label: string;
  options: TicketOptionView[];
  search_options: TicketOptionView[];
  search_label: string | null;
  search_empty: string | null;
  note_required_for: string | null;
  note_required_label: string | null;
  detail_label: string | null;
  facts: TicketFactView[];
  car_id: string | null;
  car_name: string | null;
  catalog_default: number | null;
  comparison: TicketComparisonView | null;
  status: "pending" | "needs_checking" | "answered" | "unknown";
  answer: number | string | null;
  note: string | null;
}

export interface TicketView {
  version: number;
  title: string;
  fields: TicketFieldView[];
  questions: TicketQuestionView[];
  comparison: TicketComparisonView | null;
}

export interface ViewComputedBy {
  origin: "tool" | "server";
  label: string;
  tool: string | null;
}

export interface ViewField {
  field: string;
  label: string;
}

export interface ViewInput {
  id: string;
  label: string;
  value: number | string | null;
  unit: "ils" | "percent" | "points" | "count" | "text";
  source: "employee_input" | "occupation" | "representative" | "catalog_default" | "pending_rep" | "payslip";
  ticket_field: string | null;
}

export interface ViewLine {
  key: "cash_income" | "maintenance" | "electric_gross" | "income_tax" | "national_insurance" | "health" | "employee_pension" | "employee_study" | "participation" | "family_employee_share";
  label: string;
  net_effect: number;
  inputs: string[];
  rules: ViewRule[];
}

export interface ViewRule {
  key: string;
  label: string;
}

export interface ViewWarning {
  code: string;
  message: string;
}
