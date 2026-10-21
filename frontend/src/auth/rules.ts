/** The rules the server also applies, checked before submit so the person is told early. */

export const PASSWORD_MIN = 10;
export const PASSWORD_MAX = 128;
export const PASSWORD_LENGTH_MESSAGE = "הסיסמה צריכה להיות באורך 10 עד 128 תווים";
export const PASSWORD_EMAIL_MESSAGE = "הסיסמה צריכה להיות שונה מהמייל";
export const PASSWORD_MATCH_MESSAGE = "שתי הסיסמאות צריכות להיות זהות";
export const NAME_MAX = 60;
export const CODE_LENGTH = 10;

/** Why this password cannot be used, or null. */
export function passwordProblem(password: string, email: string): string | null {
  if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
    return PASSWORD_LENGTH_MESSAGE;
  }
  if (password.trim().toLowerCase() === email.trim().toLowerCase()) return PASSWORD_EMAIL_MESSAGE;
  return null;
}

/** What the invite-code field shows as the person types or pastes: XXXXX-XXXXX, upper case. */
export function formatCodeInput(raw: string): string {
  const clean = raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, CODE_LENGTH);
  return clean.length > 5 ? `${clean.slice(0, 5)}-${clean.slice(5)}` : clean;
}
