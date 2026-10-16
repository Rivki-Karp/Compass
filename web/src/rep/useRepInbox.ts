/**
 * The representative's live inbox: GET /api/tickets/events over the fetch-based SSE client,
 * with the rep bearer. Each `tickets` event is the whole open list.
 */

import { useCallback, useEffect, useReducer, useState } from "react";
import { ticketEventsUrl } from "../api/client";
import { openStream, type StreamStatus } from "../api/sse";
import type { TicketWithView } from "../api/types";
import { initialInbox, reduceInbox, type InboxState } from "./inbox";

export interface UseRepInbox {
  state: InboxState;
  connection: StreamStatus;
  select: (ticketId: string) => void;
  answered: (ticketId: string) => void;
}

export function useRepInbox(token: string | null): UseRepInbox {
  const [state, dispatch] = useReducer(reduceInbox, initialInbox);
  // The status belongs to the token whose stream reported it: a new token starts at
  // "connecting", never at the previous token's "unauthorized".
  const [reported, setReported] = useState<{
    token: string;
    status: StreamStatus;
  } | null>(null);
  const connection: StreamStatus =
    token === null ? "closed" : reported?.token === token ? reported.status : "connecting";

  useEffect(() => {
    dispatch({ kind: "reset" });
    if (!token) return;
    return openStream({
      url: ticketEventsUrl,
      token,
      onStatus: (status) => setReported({ token, status }),
      onMessage: (message) => {
        if (message.event !== "tickets") return;
        try {
          const { tickets } = JSON.parse(message.data) as {
            tickets: TicketWithView[];
          };
          dispatch({ kind: "snapshot", tickets });
        } catch {
          // not a tickets payload (should not happen): ignore
        }
      },
    });
  }, [token]);

  const select = useCallback((ticketId: string) => dispatch({ kind: "select", ticketId }), []);
  const answered = useCallback((ticketId: string) => dispatch({ kind: "answered", ticketId }), []);
  return { state, connection, select, answered };
}
