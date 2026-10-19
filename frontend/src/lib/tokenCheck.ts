/** What the token dialogs say about a token the server checked. */

/** The server has no token for this role (empty in .env): no token typed here can work. */
export const TOKEN_NOT_CONFIGURED = "טוקן לא הוגדר בשרת. ראו docs/demo-runbook.md";

export type TokenCheck = "ok" | "wrong" | "unavailable" | "not_configured";

/** A guarded endpoint's status -> what the dialog says (503: the token is not set). */
export function tokenCheck(status: number, wrong: readonly number[] = [401, 403]): TokenCheck {
  if (status >= 200 && status < 300) return "ok";
  if (wrong.includes(status)) return "wrong";
  return status === 503 ? "not_configured" : "unavailable";
}
