/**
 * What the answer form shows when the server refuses an answer. Validation is the server's
 * (backend/compass/tools/tickets.py); the form only places its Hebrew `errors[].message` next to
 * the field it names. The English `detail` is for logs and the model, never for the rep.
 */

import { ApiError } from "../api/client";

export interface FormErrors {
  /** Tool field id -> Hebrew messages, shown under that field's input. */
  byField: Record<string, string[]>;
  /** Hebrew messages that concern the whole answer (or a field the form doesn't show). */
  form: string[];
  /** The rep token was refused: ask for it again. */
  reauth: boolean;
}

export const NO_ERRORS: FormErrors = { byField: {}, form: [], reauth: false };

const UNREADABLE = "השרת לא קיבל את התשובה. בדקו את הערכים ונסו שוב.";
const UNREACHABLE = "לא ניתן להגיע לשרת כרגע. נסו שוב.";
const TOKEN = "טוקן הנציג לא תקף יותר. הזינו אותו מחדש.";

export function answerErrors(error: unknown, fields: readonly string[]): FormErrors {
  if (!(error instanceof ApiError)) return { ...NO_ERRORS, form: [UNREACHABLE] };
  if (error.status === 401 || error.status === 403) {
    return { ...NO_ERRORS, form: [TOKEN], reauth: true };
  }
  if (!error.errors.length) {
    // e.g. FastAPI's own 422 for a malformed body: it has an English detail only
    return { ...NO_ERRORS, form: [UNREADABLE] };
  }
  const byField: Record<string, string[]> = {};
  const form: string[] = [];
  for (const e of error.errors) {
    if (e.field !== null && fields.includes(e.field)) {
      (byField[e.field] ??= []).push(e.message);
    } else {
      form.push(e.message);
    }
  }
  return { byField, form, reauth: false };
}
