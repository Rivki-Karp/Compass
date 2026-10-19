import { describe, expect, it } from "vitest";
import { MINUS, displayMinus, formatAmount, formatInput, formatSigned, spokenSigned } from "./format";

describe("formatSigned", () => {
  it("puts the sign first, with a real minus", () => {
    expect(formatSigned(2914)).toBe("+2,914");
    expect(formatSigned(-50)).toBe(`${MINUS}50`);
    expect(formatSigned(-50)).toBe("−50");
    expect(formatSigned(0)).toBe("0");
  });

  it("never emits bidi marks or a hyphen-minus", () => {
    for (const value of [2914, -50, -1938, 0, 1_234_567]) {
      expect(formatSigned(value)).not.toMatch(/[‎‏-]/);
    }
  });

  it("groups thousands", () => {
    expect(formatSigned(1_234_567)).toBe("+1,234,567");
  });
});

describe("formatAmount", () => {
  it("formats nets without a plus", () => {
    expect(formatAmount(11000)).toBe("11,000");
    expect(formatAmount(13914)).toBe("13,914");
    expect(formatAmount(0)).toBe("0");
    expect(formatAmount(-50)).toBe(`${MINUS}50`);
  });

  it("refuses to round: amounts from the API are whole", () => {
    expect(() => formatAmount(2914.5)).toThrow(/whole shekels/);
    expect(() => formatSigned(0.1)).toThrow(/whole shekels/);
  });
});

describe("spokenSigned", () => {
  it("reads the sign as a word", () => {
    expect(spokenSigned(2914)).toBe("פלוס 2,914 שקלים");
    expect(spokenSigned(-611)).toBe("מינוס 611 שקלים");
    expect(spokenSigned(0)).toBe("אפס שקלים");
  });
});

describe("formatInput", () => {
  it("formats by unit", () => {
    expect(formatInput(18500, "ils")).toBe("18,500"); // the ₪ goes outside the <bdi>
    expect(formatInput("6.5", "percent")).toBe("6.5%");
    expect(formatInput("2.75", "points")).toBe("2.75");
    expect(formatInput("2", "count")).toBe("2");
    expect(formatInput("COROLLA CROSS 2025", "text")).toBe("COROLLA CROSS 2025");
    expect(formatInput(null, "ils")).toBe("—");
  });
});

describe("displayMinus (bot bubbles, display only)", () => {
  it("a typed minus before an amount becomes U+2212", () => {
    expect(displayMinus("-286 ₪")).toBe("−286 ₪");
    expect(displayMinus("למשל MAZDA 3 (\u200E-286 ₪) ו-TUCSON (\u200E-440 ₪)")).toBe(
      "למשל MAZDA 3 (−286 ₪) ו-TUCSON (−440 ₪)",
    );
    expect(displayMinus("הפרש של -1,047 ₪ ו-(-50)")).toBe("הפרש של −1,047 ₪ ו-(−50)");
  });

  it("leaves a code, a Hebrew prefix and a list dash alone", () => {
    for (const text of ["CAR-10", "ב-300", "משתתפת ב-300 ₪", "- ויתור: +3,199 ₪", "2025-10"]) {
      expect(displayMinus(text)).toBe(text);
    }
  });
});
