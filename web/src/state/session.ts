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
  role: "employee" | "assistant";
  text: string;
  kind: PayloadByType["assistant_message"]["kind"] | null;
  turn: number | null; // index into turns (assistant messages)
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
  openTickets: [],
  lastError: null,
  between: [],
};

/** The session reached its safety limit: its latest reply is the server's fixed "limit" one. */
export function limitReached(state: SessionState): boolean {
  const replies = state.messages.filter((m) => m.role === "assistant");
  return replies[replies.length - 1]?.kind === "limit";
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
      const view = event.payload.view;
      const previous = next.comparison;
      const sameAlternative =
        previous !== null &&
        previous.view.alternative_kind === view.alternative_kind &&
        previous.view.alternative_car_id === view.alternative_car_id;
      const settles = sameAlternative && previous.view.pending && !view.pending;
      const stays = sameAlternative && previous.settled && !view.pending;
      return {
        ...next,
        comparison: {
          seq: event.seq,
          view,
          origin: event.payload.origin === "server" ? "server" : "tool",
          settled: settles || stays,
          settledSeq: settles ? event.seq : stays ? previous.settledSeq : null,
        },
      };
    }

    case "ticket_opened":
      return { ...next, openTickets: [...next.openTickets, event.payload.ticket] };

    case "ticket_answered":
      return {
        ...next,
        openTickets: next.openTickets.filter((t) => t.id !== event.payload.ticket_id),
      };

    case "session_status":
      return { ...next, status: event.payload.status };

    case "session_created":
    case "profile_updated":
    case "current_situation_set":
    case "guard_check":
      return next; // kept in the turn's events (judges mode); nothing else to show
  }
}
