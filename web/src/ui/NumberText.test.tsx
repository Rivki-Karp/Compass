import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NumberText } from "./NumberText";

const isolated = (text: string) =>
  [...render(<NumberText text={text} />).container.querySelectorAll("bdi")].map(
    (b) => b.textContent,
  );

describe("NumberText", () => {
  it("isolates signed amounts with their sign in front", () => {
    expect(isolated("הפרש של +2,914 ₪ בחודש.")).toEqual(["+2,914"]);
    expect(isolated("שינוי של −50 ₪")).toEqual(["−50"]);
  });

  it("keeps a Hebrew prefix hyphen out of the number", () => {
    expect(isolated("עולה מ-11,000 ₪ ל-13,914 ₪")).toEqual(["11,000", "13,914"]);
    expect(isolated("משתתפת ב-300 ₪.")).toEqual(["300"]);
  });

  it("isolates percentages and keeps the text intact", () => {
    const { container } = render(<NumberText text="פנסיה 6.5%, קרן 2.5%" />);
    expect([...container.querySelectorAll("bdi")].map((b) => b.textContent)).toEqual([
      "6.5%",
      "2.5%",
    ]);
    expect(container.textContent).toBe("פנסיה 6.5%, קרן 2.5%");
  });
});
