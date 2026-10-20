/**
 * Session state for the employee screen and judges mode. `reduce` is the only place it changes:
 * a pure (state, event) -> state over the server's events, in seq order. Replayed events (a
 * reconnect with Last-Event-ID, a StrictMode double effect) are ignored by seq, so applying
 * the same event twice changes nothing.
 */

import type {
  ComparisonView,
  PayloadByType,
  SessionEvent,
  Ticket,
} from "../api/types";

export interface ChatMessage {
  seq: number;
  role: "employee" | "assistant" | "rep"; // "rep": the representative's answer or note
  text: string;
  kind: PayloadByType["assistant_message"]["kind"] | null;
  turn: number | null; // index into turns (assistant messages)
  /** A "rep" message: the answers to free questions ("תשובת הנציג"), the notes otherwise. */
  rep?: RepMessage;
}

export interface RepItem {
  question: string | null;
  answer: string | null;
  note: string | null;
}

export interface RepMessage {
  kind: "answer" | "note";
  items: RepItem[];
}

/** What a ticket answer shows the employee in the chat: each free question's answer (and its
 * note); the notes on bound questions and on questions still being checked; the ticket-wide
 * note. Bound answers themselves show in the chips, not here. Null: nothing to show. */
export function repMessage(payload: PayloadByType["ticket_answered"]): RepMessage | null {
  const items: RepItem[] = [];
  let answered = false;
  for (const q of payload.questions ?? []) {
    if (q.kind === "free" && q.status === "answered") {
      answered = true;
      items.push({ question: q.prompt_he, answer: q.answer, note: q.note });
    } else if (q.note) {
      const checking = q.status === "needs_checking" ? " (בבדיקה)" : "";
      items.push({ question: q.prompt_he ? `${q.prompt_he}${checking}` : null, answer: null, note: q.note });
    }
  }
  const note = repNote(payload.answer);
  if (note) items.push({ question: null, answer: null, note });
  return items.length ? { kind: answered ? "answer" : "note", items } : null;
}

export interface ToolActivity {
  toolUseId: string;
  name: string;
  ok: boolean | null; // null while running
}

/** One agent run (agent_started .. agent_finished), with every event it produced. */
export interface Turn {
  index: number;
  trigger: PayloadByType["agent_started"]["trigger"];
  startedAt: string;
  finished: PayloadByType["agent_finished"] | null;
  tools: ToolActivity[];
  events: SessionEvent[];
  /** Events between the previous run and this one (the rep's answer, the server's settle). */
  before: SessionEvent[];
}

export interface ComparisonState {
  seq: number;
  view: ComparisonView;
  origin: "tool" | "server";
  /** Final after a pending one of the same alternative: this comparison settled it, or it
   * repeats a settled one (the server settles on the rep's answer; the model may compare again). */
  settled: boolean;
  /** The seq of the comparison that settled it (the moment to flash), or null. */
  settledSeq: number | null;
}

export interface SessionState {
  lastSeq: number;
  status: PayloadByType["session_status"]["status"];
  messages: ChatMessage[];
  turns: Turn[];
  thinking: boolean;
  thinkingSince: string | null;
  comparison: ComparisonState | null;
  /** The latest comparison of each alternative (alternativeKey), so each one settles on its own:
   * a rep answering one car of a multi-car ticket settles that car, not the others. */
  comparisons: Record<string, ComparisonState>;
  /** The alternatives the server put on screen at once (comparison_set_ready), best first. */
  optionKeys: string[];
  openTickets: Ticket[];
  lastError: string | null; // agent_error kind of the latest failed run
  /** Events since the last run finished, outside any run; the next run takes them as `before`. */
  between: SessionEvent[];
}

export const initialSession: SessionState = {
  lastSeq: 0,
  status: "active",
  messages: [],
  turns: [],
  thinking: false,
  thinkingSince: null,
  comparison: null,
  comparisons: {},
  optionKeys: [],
  openTickets: [],
  lastError: null,
  between: [],
};

/** One alternative's key: "car:CAR-10", "waiver:". */
export function alternativeKey(
  view: Pick<ComparisonView, "alternative_kind" | "alternative_car_id">,
) {
  return `${view.alternative_kind}:${view.alternative_car_id ?? ""}`;
}

/** The session reached its safety limit: its latest reply is the server's fixed "limit" one. */
export function limitReached(state: SessionState): boolean {
  const replies = state.messages.filter((m) => m.role === "assistant");
  return replies[replies.length - 1]?.kind === "limit";
}

/** The representative's free-text note in a ticket answer (answer.text), if any. */
export function repNote(answer: unknown): string | null {
  if (typeof answer !== "object" || answer === null) return null;
  const text = (answer as { text?: unknown }).text;
  return typeof text === "string" && text.trim() ? text.trim() : null;
}

/** An alternative's new comparison; it settles when its own previous one was pending. */
function nextComparison(
  state: Pick<SessionState, "comparisons">,
  seq: number,
  view: ComparisonView,
  origin: string | undefined,
): ComparisonState {
  const previous = state.comparisons[alternativeKey(view)]; // whatever came in between
  const settles = previous !== undefined && previous.view.pending && !view.pending;
  const stays = previous !== undefined && previous.settled && !view.pending;
  return {
    seq,
    view,
    origin: origin === "server" ? "server" : "tool",
    settled: settles || stays,
    settledSeq: settles ? seq : stays ? (previous.settledSeq ?? null) : null,
  };
}

function currentTurn(state: SessionState): Turn | null {
  const turn = state.turns[state.turns.length - 1];
  return turn && turn.finished === null ? turn : null;
}

function updateTurn(state: SessionState, update: (turn: Turn) => Turn): SessionState {
  const turn = currentTurn(state);
  if (!turn) return state;
  const turns = state.turns.slice(0, -1);
  turns.push(update(turn));
  return { ...state, turns };
}

export function reduce(state: SessionState, event: SessionEvent): SessionState {
  if (event.seq <= state.lastSeq) return state; // replayed: already applied
  let next: SessionState = { ...state, lastSeq: event.seq };
  if (currentTurn(next)) {
    next = updateTurn(next, (turn) => ({ ...turn, events: [...turn.events, event] }));
  } else if (event.type !== "agent_started") {
    next = { ...next, between: [...next.between, event] };
  }

  switch (event.type) {
    case "user_message":
      return {
        ...next,
        messages: [
          ...next.messages,
          {
            seq: event.seq,
            role: "employee",
            text: event.payload.content.text,
            kind: null,
            turn: null,
          },
        ],
      };

    case "assistant_message": {
      const turn = currentTurn(next);
      return {
        ...next,
        messages: [
          ...next.messages,
          {
            seq: event.seq,
            role: "assistant",
            text: event.payload.text,
            kind: event.payload.kind,
            turn: turn ? turn.index : null,
          },
        ],
      };
    }

    case "agent_started":
      return {
        ...next,
        thinking: true,
        thinkingSince: event.created_at,
        lastError: null,
        between: [],
        turns: [
          ...next.turns,
          {
            index: next.turns.length,
            trigger: event.payload.trigger,
            startedAt: event.created_at,
            finished: null,
            tools: [],
            events: [event],
            before: next.between,
          },
        ],
      };

    case "agent_finished": {
      const finished = updateTurn(next, (turn) => ({ ...turn, finished: event.payload }));
      return { ...finished, thinking: false, thinkingSince: null };
    }

    case "agent_error":
      return { ...next, lastError: event.payload.kind };

    case "tool_call":
      return updateTurn(next, (turn) => ({
        ...turn,
        tools: [
          ...turn.tools,
          { toolUseId: event.payload.tool_use_id, name: event.payload.name, ok: null },
        ],
      }));

    case "tool_result":
      return updateTurn(next, (turn) => ({
        ...turn,
        tools: turn.tools.map((tool) =>
          tool.toolUseId === event.payload.tool_use_id ? { ...tool, ok: event.payload.ok } : tool,
        ),
      }));

    case "comparison_ready": {
      const comparison = nextComparison(next, event.seq, event.payload.view, event.payload.origin);
      const key = alternativeKey(comparison.view);
      return { ...next, comparison, comparisons: { ...next.comparisons, [key]: comparison } };
    }

    case "comparison_set_ready": {
      // every option at once: each alternative's latest view, the hero left as it is
      const comparisons = { ...next.comparisons };
      const optionKeys: string[] = [];
      for (const option of event.payload.options) {
        const key = alternativeKey(option.view);
        comparisons[key] = nextComparison({ comparisons }, event.seq, option.view, "server");
        optionKeys.push(key);
      }
      return { ...next, comparisons, optionKeys };
    }

    case "ticket_opened":
      return { ...next, openTickets: [...next.openTickets, event.payload.ticket] };

    case "ticket_answered": {
      const rep = repMessage(event.payload);
      const text = rep ? rep.items.map((i) => [i.question, i.answer, i.note].filter(Boolean).join(" — ")).join("\n") : "";
      return {
        ...next,
        // a partial answer leaves the ticket open, its other fields pending
        openTickets: event.payload.partial
          ? next.openTickets
          : next.openTickets.filter((t) => t.id !== event.payload.ticket_id),
        messages: rep
          ? [...next.messages, { seq: event.seq, role: "rep", text, kind: null, turn: null, rep }]
          : next.messages,
      };
    }

    case "session_status":
      return { ...next, status: event.payload.status };

    // payslip_*: the confirmation card arrives with the UI stage; until then nothing on screen
    case "session_created":
    case "payslip_extracted":
    case "payslip_failed":
    case "payslip_confirmed":
    case "profile_updated":
    case "current_situation_set":
    case "guard_check":
      return next; // kept in the turn's events (judges mode); nothing else to show
  }
}
