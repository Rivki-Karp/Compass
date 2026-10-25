/**
 * The login (COMPASS_AUTH=1): the session token, the name and the role, kept in sessionStorage only
 * (it ends when the browser closes; never localStorage, never a cookie, never a URL). A tiny
 * external store, so apiFetch (outside React) and the components read the same login.
 */

import { useSyncExternalStore } from "react";

export type Role = "employee" | "rep" | "admin";

export interface AuthUser {
  token: string;
  name: string;
  role: Role;
  /** The login came from the demo quick access: a shared demo account. */
  demo?: boolean;
}

export interface AuthSnapshot {
  user: AuthUser | null;
  /** Why the user was sent back to the landing page, once. */
  notice: string | null;
}

export const EXPIRED_MESSAGE = "החיבור הסתיים, צריך להיכנס שוב";
const KEY = "compass.auth";

function read(): AuthUser | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthUser>;
    if (typeof parsed.token === "string" && typeof parsed.name === "string" && parsed.role) {
      return {
        token: parsed.token,
        name: parsed.name,
        role: parsed.role,
        ...(parsed.demo ? { demo: true } : {}),
      };
    }
  } catch {
    // storage blocked or not ours: logged out
  }
  return null;
}

function write(user: AuthUser | null): void {
  try {
    if (user) sessionStorage.setItem(KEY, JSON.stringify(user));
    else sessionStorage.removeItem(KEY);
  } catch {
    // storage blocked: the login lasts for this page only
  }
}

let snapshot: AuthSnapshot = { user: read(), notice: null };
const listeners = new Set<() => void>();

function publish(next: AuthSnapshot): void {
  snapshot = next;
  listeners.forEach((listener) => listener());
}

export const getAuth = (): AuthUser | null => snapshot.user;

export function setAuth(user: AuthUser): void {
  write(user);
  publish({ user, notice: null });
}

export function clearAuth(): void {
  write(null);
  publish({ user: null, notice: null });
}

/** The server no longer accepts the token (a 401): forget it and say why on the landing page. */
export function expireSession(): void {
  if (!snapshot.user) return;
  write(null);
  publish({ user: null, notice: EXPIRED_MESSAGE });
}

/** The notice has been shown. */
export function dismissNotice(): void {
  if (snapshot.notice !== null) publish({ ...snapshot, notice: null });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useAuthState(): AuthSnapshot {
  return useSyncExternalStore(subscribe, () => snapshot);
}

/** Tests: start from a given login (or none) without touching sessionStorage's other keys. */
export function resetAuthForTests(user: AuthUser | null = null): void {
  write(user);
  publish({ user, notice: null });
}
