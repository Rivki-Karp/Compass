import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BidiText } from "./BidiText";

const isolated = (text: string) =>
  [...render(<BidiText text={text} />).container.querySelectorAll("bdi")].map((b) => ({
    text: b.textContent,
    dir: b.getAttribute("dir"),
  }));
const numbers = (text: string) =>
  isolated(text)
    .filter((b) => b.dir === null)
    .map((b) => b.text);

describe("BidiText", () => {
  it("isolates signed amounts with their sign in front", () => {
    expect(numbers("הפרש של +2,914 ₪ בחודש.")).toEqual(["+2,914"]);
    expect(numbers("שינוי של −50 ₪")).toEqual(["−50"]);
    expect(isolated("הנטו עולה: +611 ₪ בחודש")).toEqual([{ text: "+611", dir: null }]);
  });

  it("keeps a Hebrew prefix hyphen out of the number", () => {
    expect(numbers("עולה מ-11,000 ₪ ל-13,914 ₪")).toEqual(["11,000", "13,914"]);
    expect(numbers("משתתפת ב-300 ₪.")).toEqual(["300"]);
  });

  it("isolates percentages and keeps the text intact", () => {
    const { container } = render(<BidiText text="פנסיה 6.5%, קרן 2.5%" />);
    expect([...container.querySelectorAll("bdi")].map((b) => b.textContent)).toEqual([
      "6.5%",
      "2.5%",
    ]);
    expect(container.textContent).toBe("פנסיה 6.5%, קרן 2.5%");
  });

  it("keeps a car name with digits as one LTR unit", () => {
    expect(isolated("מעבר ל-MG4 יעלה את הנטו")).toEqual([{ text: "MG4", dir: "ltr" }]);
    expect(isolated("רכב ATTO 3 בקבוצה")).toEqual([{ text: "ATTO 3", dir: "ltr" }]);
    expect(isolated("הקוד CAR-10.")).toEqual([{ text: "CAR-10", dir: "ltr" }]);
    expect(isolated("EV3 או KONA EV")).toEqual([
      { text: "EV3", dir: "ltr" },
      { text: "KONA EV", dir: "ltr" },
    ]);
  });

  it("leaves a Hebrew prefix out of the car name", () => {
    const { container } = render(<BidiText text="מעבר ב-ATTO 3 עכשיו" />);
    expect([...container.querySelectorAll("bdi")].map((b) => b.outerHTML)).toEqual([
      '<bdi dir="ltr">ATTO 3</bdi>',
    ]);
    expect(container.textContent).toBe("מעבר ב-ATTO 3 עכשיו");
  });

  it("keeps an amount after a car name an amount", () => {
    expect(isolated("MG4: +611 ₪ בחודש")).toEqual([
      { text: "MG4", dir: "ltr" },
      { text: "+611", dir: null },
    ]);
    expect(isolated("ATTO 3 300 ₪")).toEqual([
      { text: "ATTO 3", dir: "ltr" },
      { text: "300", dir: null },
    ]);
    expect(isolated("MODEL 3 12 ₪")).toEqual([
      { text: "MODEL 3", dir: "ltr" },
      { text: "12", dir: null },
    ]);
  });
});
