/**
 * The one way to the API: every REST call and SSE stream URL is built here.
 *
 * VITE_API_BASE_URL is the backend's public URL (both on Render: the UI a static site, the API a
 * web service), baked in at build time. Empty (dev, and the local single-origin demo) means the same origin:
 * Vite proxies /api in dev, FastAPI serves the build in the demo.
 */

import { expireSession, getAuth, type Role } from "../auth/authStore";
import type {
  AnswerError,
  Health,
  JudgesStats,
  PayloadByType,
  PayslipConfirmed,
  TicketWithView,
} from "./types";

/** One question's answer in POST /tickets/{id}/answer (`answers`). */
export type QuestionAnswer =
  | { value: string; note?: string }
  | { status: "needs_checking"; note?: string };

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

/** An API URL: `apiUrl("/health")` is `${VITE_API_BASE_URL}/api/health`. */
export const apiUrl = (path: string) => `${API_BASE}/api${path}`;

/**
 * fetch() to the API, for a caller that needs the raw Response (its status). With a login
 * (COMPASS_AUTH=1) it adds `Authorization: Bearer <session token>` unless the caller set one, and
 * a 401 to such a call means the login has ended: it is forgotten and the app goes back to the
 * landing page. Without a login nothing changes.
 */
export const apiFetch = async (path: string, init: RequestInit = {}): Promise<Response> => {
  const auth = getAuth();
  if (!auth || new Headers(init.headers).has("Authorization")) return fetch(apiUrl(path), init);
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${auth.token}`);
  const response = await fetch(apiUrl(path), { ...init, headers });
  if (response.status === 401) expireSession();
  return response;
};

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

/** POST /sessions/{id}/current-car: what the employee chose in the catalog picker. */
export type CarPick =
  | { choice: "car" | "check_year"; car_id: string }
  | { choice: "not_in_list" | "no_car" };

/** What register and login answer: the session token (shown once), the name and the role. */
export interface Granted {
  token: string;
  name: string;
  role: Role;
}

/** GET /conversations: one entry of the user's own list. */
export interface ConversationEntry {
  id: string;
  title: string;
  updated_at: string;
  status: "final" | "pending" | "partial" | "none";
  diff: number | null;
}

/** What the admin may know of a person (GET /admin/users). */
export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  status: "active" | "disabled";
  created_at: string;
  last_login_at: string | null;
}

export interface InviteCreated {
  code: string;
  email: string;
  role: Role;
  expires_at: string;
}

export const api = {
  health: () => request<Health>("/health"),
  login: (email: string, password: string) =>
    request<Granted>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (body: { email: string; code: string; name: string; password: string }) =>
    request<Granted>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request<null>("/auth/logout", { method: "POST" }),
  me: () => request<{ name: string; role: Role }>("/auth/me"),
  conversations: () => request<ConversationEntry[]>("/conversations"),
  deleteConversation: (id: string) => request<null>(`/conversations/${id}`, { method: "DELETE" }),
  adminUsers: () => request<AdminUser[]>("/admin/users"),
  invite: (email: string, role: Role) =>
    request<InviteCreated>("/admin/invites", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),
  patchUser: (id: string, change: { role?: Role; status?: "active" | "disabled" }) =>
    request<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(change) }),
  deleteUser: (id: string) => request<null>(`/admin/users/${id}`, { method: "DELETE" }),
  createSession: () => request<{ id: string }>("/sessions", { method: "POST" }),
  postMessage: (sessionId: string, text: string) =>
    request<{ message_seq: number }>(`/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  pickCurrentCar: (sessionId: string, pick: CarPick) =>
    request<{ outcome: string }>(`/sessions/${sessionId}/current-car`, {
      method: "POST",
      body: JSON.stringify(pick),
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

export type PayslipCandidate = Pick<PayloadByType["payslip_extracted"], "fields" | "dropped_keys">;

/**
 * POST the file itself as the body (never multipart). `onSent` fires once the bytes are out and
 * the server is reading the payslip. Rejects with ApiError (its Hebrew `errors`) on a refusal.
 */
export function uploadPayslip(
  sessionId: string,
  file: Blob,
  onSent: () => void,
): Promise<PayslipCandidate> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", apiUrl(`/sessions/${sessionId}/payslip`));
    xhr.setRequestHeader("Content-Type", file.type);
    const auth = getAuth();
    if (auth) xhr.setRequestHeader("Authorization", `Bearer ${auth.token}`);
    xhr.upload.onload = onSent;
    xhr.onload = () => {
      if (auth && xhr.status === 401) expireSession();
      let body: { detail?: unknown; errors?: AnswerError[] } | PayslipCandidate | null = null;
      try {
        body = JSON.parse(xhr.responseText) as typeof body;
      } catch {
        body = null;
      }
      if (xhr.status === 201 && body) resolve(body as PayslipCandidate);
      else {
        const parsed = (body ?? {}) as { detail?: unknown; errors?: AnswerError[] };
        reject(new ApiError(xhr.status, parsed.detail, parsed.errors ?? []));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "network"));
    xhr.send(file);
  });
}

export const confirmPayslip = (sessionId: string, fields: Record<string, string>) =>
  request<PayslipConfirmed>(`/sessions/${sessionId}/payslip/confirm`, {
    method: "POST",
    body: JSON.stringify({ fields }),
  });

export const sessionEventsUrl = (sessionId: string) => apiUrl(`/sessions/${sessionId}/events`);
export const ticketEventsUrl = apiUrl("/tickets/events");
