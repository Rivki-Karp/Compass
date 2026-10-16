/**
 * The employee's session: create (or resume) it, stream its events into the reducer, send
 * messages. The session id lives in sessionStorage so a refresh resumes the conversation (the
 * stream replays every event from the start); it is not a secret.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, sessionEventsUrl } from "../api/client";
import type { SessionEvent } from "../api/types";
import { openStream, type StreamStatus } from "../api/sse";
import { initialSession, reduce, type SessionState } from "./session";

const SESSION_KEY = "compass.session";

function storedSession(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

function storeSession(id: string | null): void {
  try {
    if (id) sessionStorage.setItem(SESSION_KEY, id);
    else sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // storage blocked: the session lasts for this page only
  }
}

type Action = { kind: "event"; event: SessionEvent } | { kind: "reset" };

function sessionReducer(state: SessionState, action: Action): SessionState {
  return action.kind === "reset" ? initialSession : reduce(state, action.event);
}

export interface SendFailure {
  text: string;
}

export interface UseSession {
  sessionId: string | null;
  state: SessionState;
  connection: StreamStatus;
  /** A message was posted and its run hasn't started yet. */
  sending: boolean;
  sendFailure: SendFailure | null;
  send: (text: string) => void;
}

/** `adminToken`: open the stream with it (judges mode gets the full events). */
export function useSession(adminToken: string | null): UseSession {
  const [sessionId, setSessionId] = useState<string | null>(storedSession);
  const [state, dispatch] = useReducer(sessionReducer, initialSession);
  const [connection, setConnection] = useState<StreamStatus>("connecting");
  const [sending, setSending] = useState(false);
  const [sendFailure, setSendFailure] = useState<SendFailure | null>(null);
  const creating = useRef(false);

  // No session yet: create one.
  useEffect(() => {
    if (sessionId || creating.current) return;
    creating.current = true;
    api
      .createSession()
      .then(({ id }) => {
        storeSession(id);
        setSessionId(id);
      })
      .catch(() => setConnection("reconnecting"))
      .finally(() => {
        creating.current = false;
      });
  }, [sessionId]);

  // Stream the session's events (replayed from the start on every (re)open).
  useEffect(() => {
    if (!sessionId) return;
    dispatch({ kind: "reset" });
    const close = openStream({
      url: sessionEventsUrl(sessionId),
      token: adminToken,
      onStatus: (status) => {
        if (status === "gone") {
          // 404: the server no longer knows this session (e.g. a fresh database)
          storeSession(null);
          setSessionId(null);
          return;
        }
        setConnection(status);
      },
      onMessage: (message) => {
        try {
          dispatch({ kind: "event", event: JSON.parse(message.data) as SessionEvent });
        } catch {
          // not an event (should not happen): ignore
        }
      },
    });
    return close;
  }, [sessionId, adminToken]);

  // The run started (or finished): the message is no longer "sending".
  useEffect(() => {
    if (state.thinking) setSending(false);
  }, [state.thinking, state.turns.length]);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!sessionId || !trimmed) return;
      setSendFailure(null);
      setSending(true);
      api.postMessage(sessionId, trimmed).catch(() => {
        setSending(false);
        setSendFailure({ text: trimmed });
      });
    },
    [sessionId],
  );

  return { sessionId, state, connection, sending, sendFailure, send };
}
