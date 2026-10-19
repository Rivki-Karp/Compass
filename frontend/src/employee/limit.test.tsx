/** The session safety limit (Day 5 Stage 3): the "שיחה חדשה" button and a fresh session. */

import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionEvent } from "../api/types";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { initialSession, limitReached, reduce } from "../state/session";
import { ChatPanel } from "./ChatPanel";

const LIMIT_TEXT = "השיחה הגיעה לאורך המרבי. אפשר להתחיל שיחה חדשה.";
const walkthrough = walkthroughLog as unknown as SessionEvent[];
const sid = walkthrough[0]?.session_id ?? "s";

let seq = walkthrough.at(-1)?.seq ?? 0;
function ev<T extends SessionEvent["type"]>(type: T, payload: unknown): SessionEvent {
  seq += 1;
  return { session_id: sid, seq, type, payload, created_at: "2026-10-18T10:00:00Z" } as SessionEvent;
}

/** A limited run, as the server emits it: started, the fixed reply, finished. */
const limitRun = () => [
  ev("user_message", { message_seq: seq + 1, content: { text: "עוד שאלה" } }),
  ev("agent_started", { trigger: "employee_turn" }),
  ev("assistant_message", { message_seq: seq + 1, text: LIMIT_TEXT, kind: "limit", comparison_ref: null }),
  ev("agent_finished", { outcome: "limit" }),
];

describe("limitReached", () => {
  it("is false for an ordinary session and true once the latest reply is the limit reply", () => {
    const before = walkthrough.reduce(reduce, initialSession);
    expect(limitReached(initialSession)).toBe(false);
    expect(limitReached(before)).toBe(false);

    const after = limitRun().reduce(reduce, before);
    expect(limitReached(after)).toBe(true);
    expect(after.thinking).toBe(false); // the run finished: no endless "מחשב…"
    expect(after.comparison?.view.display_diff).toBe(2914); // the result stays on screen
  });

  it("an employee message after it does not hide the button; only a real reply would", () => {
    const limited = limitRun().reduce(reduce, walkthrough.reduce(reduce, initialSession));
    const typed = reduce(limited, ev("user_message", { message_seq: seq + 1, content: { text: "?" } }));
    expect(limitReached(typed)).toBe(true);
    const replied = reduce(
      typed,
      ev("assistant_message", { message_seq: seq + 1, text: "תשובה", kind: "reply", comparison_ref: null }),
    );
    expect(limitReached(replied)).toBe(false);
  });
});

describe("ChatPanel at the limit", () => {
  const props = {
    messages: [],
    turns: [],
    thinking: false,
    suggestions: ["הצעה"],
    failedText: null,
    onSend: () => {},
  };

  it("shows the input and suggestions until the limit", () => {
    render(<ChatPanel {...props} />);
    expect(screen.getByLabelText("הודעה")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "שיחה חדשה" })).toBeNull();
  });

  it("replaces them with a focused 'שיחה חדשה' button that starts a new session", async () => {
    const onNewSession = vi.fn();
    render(<ChatPanel {...props} limitReached onNewSession={onNewSession} />);
    const button = screen.getByRole("button", { name: "שיחה חדשה" });
    expect(button).toHaveFocus();
    expect(screen.queryByLabelText("הודעה")).toBeNull();
    expect(screen.queryByRole("button", { name: "הצעה" })).toBeNull();
    await userEvent.setup().click(button);
    expect(onNewSession).toHaveBeenCalledOnce();
  });
});

// useSession with the network mocked: newSession forgets the stored id and creates a new one.
const createSession = vi.fn();
vi.mock("../api/client", () => ({
  api: { createSession: () => createSession() },
  sessionEventsUrl: (id: string) => `/api/sessions/${id}/events`,
}));
const opened: string[] = [];
vi.mock("../api/sse", () => ({
  openStream: (options: { url: string }) => {
    opened.push(options.url);
    return () => {};
  },
}));

describe("useSession.newSession", () => {
  beforeEach(() => {
    sessionStorage.clear();
    opened.length = 0;
    createSession.mockReset();
  });

  it("starts a fresh session and streams it", async () => {
    const { useSession } = await import("../state/useSession");
    createSession.mockResolvedValueOnce({ id: "first" }).mockResolvedValueOnce({ id: "second" });
    const { result } = renderHook(() => useSession(null));
    await waitFor(() => expect(result.current.sessionId).toBe("first"));
    expect(sessionStorage.getItem("compass.session")).toBe("first");

    act(() => result.current.newSession());
    await waitFor(() => expect(result.current.sessionId).toBe("second"));
    expect(sessionStorage.getItem("compass.session")).toBe("second");
    expect(createSession).toHaveBeenCalledTimes(2);
    expect(opened.at(-1)).toBe("/api/sessions/second/events");
    expect(result.current.state.messages).toEqual([]);
  });
});
