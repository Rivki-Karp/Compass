/**
 * The one way to the API: every REST call and SSE stream URL is built here.
 *
 * VITE_API_BASE_URL is the backend's public URL (both on Render: the UI a static site, the API a
 * web service), baked in at build time. Empty (dev, and the local single-origin demo) means the same origin:
 * Vite proxies /api in dev, FastAPI serves the build in the demo.
 */

import type { AnswerError, Health, JudgesStats, TicketWithView } from "./types";

/** One question's answer in POST /tickets/{id}/answer (`answers`). */
export type QuestionAnswer =
  | { value: string; note?: string }
  | { status: "needs_checking"; note?: string };

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

/** An API URL: `apiUrl("/health")` is `${VITE_API_BASE_URL}/api/health`. */
export const apiUrl = (path: string) => `${API_BASE}/api${path}`;

/** fetch() to the API, for a caller that needs the raw Response (its status). */
export const apiFetch = (path: string, init: RequestInit = {}) => fetch(apiUrl(path), init);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
    readonly errors: AnswerError[] = [],
  ) {
    super(`API ${status}`);
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await apiFetch(path, { ...init, headers });
  const body: unknown = response.headers.get("content-type")?.includes("json")
    ? await response.json()
    : null;
  if (!response.ok) {
    const parsed = (body ?? {}) as { detail?: unknown; errors?: AnswerError[] };
    throw new ApiError(response.status, parsed.detail, parsed.errors ?? []);
  }
  return body as T;
}

export const api = {
  health: () => request<Health>("/health"),
  createSession: () => request<{ id: string }>("/sessions", { method: "POST" }),
  postMessage: (sessionId: string, text: string) =>
    request<{ message_seq: number }>(`/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  judgesStats: (token: string) => request<JudgesStats>("/admin/stats", {}, token),
  openTickets: (token: string) => request<TicketWithView[]>("/tickets?status=open", {}, token),
  /** Answer some of a ticket's questions (by question id); the others stay pending. Each is a
   * value or needs_checking, with an optional note. */
  answerQuestions: (token: string, ticketId: string, answers: Record<string, QuestionAnswer>) =>
    request<unknown>(
      `/tickets/${ticketId}/answer`,
      { method: "POST", body: JSON.stringify({ answers, partial: true }) },
      token,
    ),
  /** `note`: the rep's free text to the employee (answer_text); it never changes a value.
   * `partial`: only these fields; the others stay pending and the ticket stays open. */
  answerTicket: (
    token: string,
    ticketId: string,
    values: Record<string, unknown>,
    note?: string,
    partial = false,
  ) =>
    request<unknown>(
      `/tickets/${ticketId}/answer`,
      {
        method: "POST",
        body: JSON.stringify({
          values,
          ...(note ? { answer_text: note } : {}),
          ...(partial ? { partial: true } : {}),
        }),
      },
      token,
    ),
};

export const sessionEventsUrl = (sessionId: string) => apiUrl(`/sessions/${sessionId}/events`);
export const ticketEventsUrl = apiUrl("/tickets/events");
