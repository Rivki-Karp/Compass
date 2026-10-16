/**
 * The representative's inbox state (brief §4.6). `reduceInbox` is the only place it changes.
 *
 * The server's `tickets` event is the whole open list each time (no replay, no seq), so a
 * snapshot replaces the list. A ticket the rep has just answered is dropped at once, and stays
 * dropped even if a snapshot taken before the answer arrives after it.
 */

import type { TicketWithView } from "../api/types";

export interface InboxState {
  tickets: TicketWithView[];
  selectedId: string | null;
  /** Answered from this tab: never shown again, whatever a late snapshot says. */
  answeredIds: string[];
  /** At least one snapshot arrived (before that, the list is loading, not empty). */
  loaded: boolean;
  /** Select the first ticket when none is selected: until the rep answers one. After that the
   * screen shows the confirmation, not another ticket that may look just like the answered one. */
  autoSelect: boolean;
}

export const initialInbox: InboxState = {
  tickets: [],
  selectedId: null,
  answeredIds: [],
  loaded: false,
  autoSelect: true,
};

export type InboxAction =
  | { kind: "snapshot"; tickets: TicketWithView[] }
  | { kind: "select"; ticketId: string }
  | { kind: "answered"; ticketId: string }
  | { kind: "reset" };

/** Keep the selection while its ticket is open; otherwise the first (oldest) one, or none. */
function withSelection(state: InboxState): InboxState {
  const { tickets, selectedId } = state;
  if (selectedId !== null && tickets.some((t) => t.id === selectedId)) return state;
  return {
    ...state,
    selectedId: state.autoSelect ? (tickets[0]?.id ?? null) : null,
  };
}

export function reduceInbox(state: InboxState, action: InboxAction): InboxState {
  switch (action.kind) {
    case "snapshot":
      return withSelection({
        ...state,
        loaded: true,
        tickets: action.tickets.filter((t) => !state.answeredIds.includes(t.id)),
      });
    case "select":
      return state.tickets.some((t) => t.id === action.ticketId)
        ? { ...state, selectedId: action.ticketId }
        : state;
    case "answered":
      return {
        ...state,
        tickets: state.tickets.filter((t) => t.id !== action.ticketId),
        answeredIds: [...state.answeredIds, action.ticketId],
        selectedId: null,
        autoSelect: false,
      };
    case "reset":
      return initialInbox;
  }
}

export function selectedTicket(state: InboxState): TicketWithView | null {
  return state.tickets.find((t) => t.id === state.selectedId) ?? null;
}

/** "עכשיו", "לפני 2 דק'", "לפני 3 שע'", "לפני 2 ימים": how long a ticket has been open. */
export function ticketAge(createdAt: string, now: number): string {
  const minutes = Math.floor((now - Date.parse(createdAt)) / 60_000);
  if (!(minutes >= 1)) return "עכשיו"; // also a clock a little behind the server's
  if (minutes < 60) return `לפני ${minutes} דק'`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `לפני ${hours} שע'`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "לפני יום" : `לפני ${days} ימים`;
}
