/**
 * Rep/admin tokens: entered once in the UI and kept in sessionStorage only (brief §0): never
 * localStorage, never in a URL or a log. Gone when the tab closes.
 */

export type TokenRole = "admin" | "rep";

const KEY: Record<TokenRole, string> = {
  admin: "compass.token.admin",
  rep: "compass.token.rep",
};

export function getToken(role: TokenRole): string | null {
  try {
    return sessionStorage.getItem(KEY[role]);
  } catch {
    return null;
  }
}

export function setToken(role: TokenRole, token: string): void {
  try {
    sessionStorage.setItem(KEY[role], token);
  } catch {
    // storage blocked: the token lasts for this page only
  }
}

export function clearToken(role: TokenRole): void {
  try {
    sessionStorage.removeItem(KEY[role]);
  } catch {
    // nothing stored
  }
}
