import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import type { AnswerError } from "../api/types";
import negative from "../test/fixtures/e001_answer_negative.json";
import { answerErrors } from "./answerErrors";

const FIELD = "alternative_participation:CAR-10";
const all = (e: ReturnType<typeof answerErrors>) => [...Object.values(e.byField).flat(), ...e.form];

describe("answerErrors", () => {
  it("puts the server's Hebrew message next to its field (the real 422 for -50)", () => {
    const error = new ApiError(422, negative.detail, negative.errors as AnswerError[]);
    const mapped = answerErrors(error, [FIELD]);
    expect(mapped.byField[FIELD]).toEqual(["הערך צריך להיות בין 0 ל-20,000."]);
    expect(mapped.form).toEqual([]);
    expect(mapped.reauth).toBe(false);
  });

  it("never shows the English detail", () => {
    const error = new ApiError(422, negative.detail, negative.errors as AnswerError[]);
    const shown = all(answerErrors(error, [FIELD])).join(" ");
    expect(shown).not.toContain("must be");
    expect(String(negative.detail)).toContain("must be"); // the fixture does carry one
  });

  it("errors without a field (or for a field the form doesn't show) go to the form", () => {
    const error = new ApiError(409, "ticket x is already answered", [
      {
        code: "ticket_already_answered",
        field: null,
        message: "כבר נענה על הטיקט הזה.",
      },
      {
        code: "not_a_blocking_field",
        field: "base_salary",
        message: "השדה הזה לא שייך לטיקט.",
      },
    ]);
    const mapped = answerErrors(error, [FIELD]);
    expect(mapped.byField).toEqual({});
    expect(mapped.form).toEqual(["כבר נענה על הטיקט הזה.", "השדה הזה לא שייך לטיקט."]);
  });

  it("collects several messages for one field", () => {
    const error = new ApiError(
      422,
      [],
      [
        { code: "a", field: FIELD, message: "א" },
        { code: "b", field: FIELD, message: "ב" },
      ],
    );
    expect(answerErrors(error, [FIELD]).byField[FIELD]).toEqual(["א", "ב"]);
  });

  it("a 422 with an English detail only (FastAPI's own) shows a Hebrew generic message", () => {
    const error = new ApiError(422, [{ msg: "Input should be a valid dictionary" }]);
    const mapped = answerErrors(error, [FIELD]);
    expect(mapped.form).toEqual(["השרת לא קיבל את התשובה. בדקו את הערכים ונסו שוב."]);
    expect(all(mapped).join(" ")).not.toContain("Input");
  });

  it("a refused token asks for it again", () => {
    const mapped = answerErrors(new ApiError(401, "invalid token"), [FIELD]);
    expect(mapped.reauth).toBe(true);
    expect(mapped.form).toEqual(["טוקן הנציג לא תקף יותר. הזינו אותו מחדש."]);
  });

  it("a network failure says the server can't be reached", () => {
    const mapped = answerErrors(new TypeError("Failed to fetch"), [FIELD]);
    expect(mapped.form).toEqual(["לא ניתן להגיע לשרת כרגע. נסו שוב."]);
    expect(mapped.reauth).toBe(false);
  });
});
