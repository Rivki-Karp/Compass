/**
 * Judges mode's engine room (brief §4.5): one run's events, as cards. Pure, so it is tested on
 * the real demo logs. Admin-only fields (tool input and result, guard numbers and draft, usage)
 * are present only when the stream was opened with the admin token; without them the cards say
 * less, they never guess.
 */

import type { ComparisonView, GuardCheckPayload, PayloadByType } from "../api/types";
import type { Turn } from "../state/session";

export type EngineCard =
  | {
      kind: "rep_answer";
      seq: number;
      values: Record<string, unknown>;
      unknown: string[];
    }
  | {
      kind: "tool";
      seq: number;
      name: string;
      ok: boolean | null; // null: no result yet
      input: Record<string, unknown> | null;
      result: Record<string, unknown> | null;
    }
  | {
      kind: "comparison";
      seq: number;
      view: ComparisonView;
      /** "server": recomputed by the server, no model call (a ticket opened or was answered). */
      origin: "tool" | "server";
    }
  | { kind: "guard"; seq: number; guard: GuardCheckPayload }
  | { kind: "template"; seq: number; text: string }
  | { kind: "error"; seq: number; error: string; message: string | null };

export function engineCards(turn: Turn): EngineCard[] {
  const cards: EngineCard[] = [];
  const tools = new Map<string, Extract<EngineCard, { kind: "tool" }>>();
  for (const event of [...turn.before, ...turn.events]) {
    switch (event.type) {
      case "ticket_answered":
        cards.push({
          kind: "rep_answer",
          seq: event.seq,
          values: answerValues(event.payload),
          unknown: event.payload.unknown,
        });
        break;
      case "tool_call": {
        const card = {
          kind: "tool" as const,
          seq: event.seq,
          name: event.payload.name,
          ok: null,
          input: event.payload.input ?? null,
          result: null,
        };
        tools.set(event.payload.tool_use_id, card);
        cards.push(card);
        break;
      }
      case "tool_result": {
        const card = tools.get(event.payload.tool_use_id);
        if (card) {
          card.ok = event.payload.ok;
          card.result = event.payload.result ?? null;
        }
        break;
      }
      case "comparison_ready":
        cards.push({
          kind: "comparison",
          seq: event.seq,
          view: event.payload.view,
          origin: event.payload.origin === "server" ? "server" : "tool",
        });
        break;
      case "guard_check":
        cards.push({ kind: "guard", seq: event.seq, guard: event.payload });
        break;
      case "assistant_message":
        if (event.payload.kind === "template") {
          cards.push({ kind: "template", seq: event.seq, text: event.payload.text });
        }
        break;
      case "agent_error":
        cards.push({
          kind: "error",
          seq: event.seq,
          error: event.payload.kind,
          message: event.payload.message ?? null,
        });
        break;
      default:
        break;
    }
  }
  return cards;
}

function answerValues(payload: PayloadByType["ticket_answered"]): Record<string, unknown> {
  const answer = payload.answer as { values?: Record<string, unknown> } | null;
  return answer?.values ?? {};
}

/** "4 מתוך 4 אומתו · נשלח" and friends: what the guard decided, in words. */
export function guardVerdict(guard: GuardCheckPayload): string {
  const numbers = guard.numbers ?? [];
  const bad = guard.violations ?? [];
  const checked =
    numbers.length === 0
      ? "אין מספרים בתשובה"
      : `${numbers.length - bad.length} מתוך ${numbers.length} אומתו`;
  switch (guard.action) {
    case "accept":
      return `${checked} · נשלח`;
    case "accept_after_retry":
      return `${checked} · נשלח אחרי ניסוח מחדש`;
    case "retry":
      return `${checked} · נדחה, המודל מנסח מחדש בלי כלים`;
    case "template":
      return `${checked} · נדחה שוב, נשלחה תשובה מתבנית`;
  }
}

/** Where a verified number came from, as the guard recorded it. Tool names stay as they are. */
export function sourceLabel(source: string): string {
  switch (source) {
    case "employee":
      return "העובד/ת";
    case "representative":
      return "נציג";
    case "harmless":
      return "שנה או ספירה";
    default:
      return source;
  }
}
