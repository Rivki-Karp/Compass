/** The REST side of the API (same origin: Vite proxies /api in dev, FastAPI serves the build). */

import type { AnswerError, Health, JudgesStats, TicketWithView } from "./types";

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
  const response = await fetch(`/api${path}`, { ...init, headers });
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

export const sessionEventsUrl = (sessionId: string) => `/api/sessions/${sessionId}/events`;
export const ticketEventsUrl = "/api/tickets/events";
