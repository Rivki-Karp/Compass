// Generated from the Pydantic models by `uv run python tasks.py ts-types`. Do not edit.
// Source: compass/tools/view.py (views), compass/state/store.py (event types).

export const EVENT_TYPES = [
  "agent_error",
  "agent_finished",
  "agent_started",
  "assistant_message",
  "comparison_ready",
  "current_situation_set",
  "guard_check",
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
  group: string | null;
  group_label: string | null;
  group_budget: number | null;
  today_net: number | null;
  alternative_net: number | null;
  display_diff: number;
  direction: "up" | "down" | "flat";
  breakdown: ViewLine[];
  inputs: ViewInput[];
  pending: boolean;
  pending_fields: string[];
  partial: boolean;
  missing: ViewField[];
  warnings: ViewWarning[];
  hypothetical: boolean;
  rules_version: string;
}

export interface TicketComparisonView {
  alternative_title: string;
  display_diff: number;
  pending: boolean;
}

export interface TicketFieldView {
  field: string;
  label: string;
  unit: "ils" | "percent" | "points" | "count" | "text";
  car_id: string | null;
  car_name: string | null;
  catalog_default: number | null;
}

export interface TicketView {
  version: number;
  title: string;
  fields: TicketFieldView[];
  comparison: TicketComparisonView | null;
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
  source: "employee_input" | "occupation" | "representative" | "catalog_default" | "pending_rep";
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
