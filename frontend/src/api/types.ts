/**
 * API types that are not Pydantic models: the SSE envelope, event payloads, health, tickets.
 * The view models and the event type names are generated (./generated.ts) from the server.
 *
 * Event names are the server's (stored in the events table); the brief's names map onto them:
 *
 *   brief               server event
 *   employee_message    user_message
 *   assistant_message   assistant_message
 *   turn_started        agent_started
 *   turn_finished       agent_finished      (also carries the brief's `usage`)
 *   usage               agent_finished      (usage, cost_usd: admin only)
 *   tool_call           tool_call           (input: admin only)
 *   tool_result         tool_result         (summary, result: admin only)
 *   comparison_ready    comparison_ready    (with `view`; also the server's pending recompute)
 *   ticket_opened       ticket_opened
 *   ticket_answered     ticket_answered
 *   guard_verdict       guard_check         (numbers, violations, sources, draft: admin only)
 *   template_fallback   guard_check with action "template", then assistant_message kind "template"
 *   error               agent_error         (message: admin only)
 *
 * Fields marked "admin only" are present only when the stream was opened with the admin token.
 */

import type { ComparisonView, EventType, TicketView } from "./generated";

export type { ComparisonView, EventType, TicketView } from "./generated";
export type {
  TicketComparisonView,
  TicketFieldView,
  TicketOptionView,
  TicketQuestionView,
  ViewField,
  ViewInput,
  ViewLine,
  ViewRule,
  ViewWarning,
} from "./generated";

export type ChipSource = ComparisonView["inputs"][number]["source"];
export type Unit = ComparisonView["inputs"][number]["unit"];
export type Direction = ComparisonView["direction"];

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
}

export interface Ticket {
  id: string;
  session_id: string;
  question: string;
  context: Record<string, unknown>;
  blocking_fields: string[];
  quick_answers: { id: string; label: string; values: Record<string, unknown> }[];
  status: "open" | "answered";
  answer: unknown;
  created_at: string;
  answered_at: string | null;
}

export interface TicketWithView extends Ticket {
  view: TicketView;
}

export interface GuardCheckPayload {
  passed: boolean;
  action: "accept" | "retry" | "accept_after_retry" | "template";
  // admin only
  numbers?: string[];
  violations?: string[];
  sources?: Record<string, string>;
  rejected_draft?: string;
}

export interface PayloadByType {
  session_created: { status: string };
  session_status: { status: "active" | "waiting_for_rep" | "closed" };
  user_message: { message_seq: number; content: { text: string } };
  assistant_message: {
    message_seq: number;
    text: string;
    // "limit": the session safety limit's fixed reply (no model call); the UI offers a new chat
    kind: "reply" | "template" | "error" | "limit";
    comparison_ref: number | null;
  };
  profile_updated: {
    fields: Record<string, { state: string; source: string; value: unknown }>;
  };
  current_situation_set: { scenario: Record<string, unknown> };
  comparison_ready: {
    alternative_kind: string;
    alternative: Record<string, unknown>;
    view: ComparisonView;
    pending_rep: boolean;
    origin?: "server";
    recomputed_from?: number;
    ticket_id?: string;
    pending_field?: string;
    answered_field?: string; // the server settled it when the rep answered this field
    [key: string]: unknown;
  };
  comparison_set_ready: {
    origin: "server";
    tool: "list_options";
    // every eligible alternative, best first, each with the view compare would give it
    options: { alternative: Record<string, unknown>; view: ComparisonView }[];
  };
  ticket_opened: { ticket: Ticket };
  ticket_answered: {
    ticket_id: string;
    answer: unknown; // this answer (one part of a partial one)
    fields: Record<string, unknown>;
    unknown: string[];
    partial?: boolean; // the ticket stays open: `pending` fields still wait for the rep
    pending?: string[];
    // this part's answer to each question, display-ready (tickets with questions)
    questions?: {
      id: string;
      kind: "bound" | "free";
      bound_field: string | null;
      prompt_he: string;
      status: "answered" | "needs_checking" | "unknown";
      value: unknown;
      answer: string | null; // an option's label ("כן"), the text, or the value as text
      note: string | null;
    }[];
  };
  agent_started: { trigger: "employee_turn" | "rep_answer" };
  agent_finished: {
    outcome: "reply" | "template" | "error" | "limit";
    // admin only
    error?: string | null;
    limit?: "turns" | "input_tokens" | null;
    rounds?: number;
    latency_ms?: number;
    model?: string | null;
    usage?: Usage;
    cost_usd?: number | null;
  };
  tool_call: {
    tool_use_id: string;
    name: string;
    input?: Record<string, unknown>; // admin only
  };
  tool_result: {
    tool_use_id: string;
    name: string;
    ok: boolean;
    summary?: Record<string, unknown>; // admin only
    result?: Record<string, unknown>; // admin only
  };
  guard_check: GuardCheckPayload;
  agent_error: { kind: string; message?: string };
  // The payslip upload (COMPASS_PAYSLIP=1): a pending candidate the employee confirms, numbers
  // and flags only (never the file), or why reading it failed.
  payslip_extracted: {
    fields: Record<string, PayslipCandidateField>;
    dropped_keys: number;
    // admin only
    model?: string | null;
    fallback?: boolean;
    latency_ms?: number;
    cost_usd?: number | null;
  };
  payslip_failed: { code: string };
}

export interface PayslipCandidateField {
  value: string | null; // a Decimal as text (or YYYY-MM); null when unknown or flagged
  confidence: "high" | "medium" | "low";
  flag: "wrong_type" | "out_of_range" | "too_many_decimals" | "not_a_step" | "invalid" | null;
}

/** One event as the session stream sends it (`data` of an SSE message). */
export type SessionEvent = {
  [T in EventType]: {
    session_id: string;
    seq: number;
    type: T;
    payload: PayloadByType[T];
    created_at: string;
  };
}[EventType];

export interface DemoScript {
  name: string;
  title: string;
  messages: string[];
}

export interface Health {
  ok: boolean;
  llm: "anthropic" | "scripted" | "none";
  demo_scripts: DemoScript[] | null;
  dev_tools: boolean;
  /** Whether each token is set on the server (never its value). */
  auth?: { rep: boolean; admin: boolean };
}

/** GET /api/admin/stats: judges mode's tiles, from committed files. Money is display-ready
 * USD strings; a part is null when its file is missing. */
export interface JudgesStats {
  evals: {
    run_at: string;
    model: string;
    effort: string;
    repeat: number;
    scenarios_passed: number;
    scenarios_total: number;
    runs_passed: number;
    runs_total: number;
  } | null;
  spend: { total_usd: string; calls: number; cap_usd: string | null } | null;
  tests: { pytest: number; vitest: number; e2e?: number; as_of: string } | null;
  cost_per_conversation: { usd: string; runs: number } | null;
}

export interface AnswerError {
  code: string;
  field: string | null;
  message: string; // Hebrew
}
