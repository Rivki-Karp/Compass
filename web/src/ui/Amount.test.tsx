import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Amount } from "./Amount";

describe("Amount", () => {
  it("wraps the number in <bdi> so the sign stays in front in RTL", () => {
    const { container } = render(
      <p dir="rtl">
        הפרש של <Amount value={2914} signed currency /> בחודש
      </p>,
    );
    const bdi = container.querySelector("bdi");
    expect(bdi?.textContent).toBe("+2,914"); // the number alone, sign first
    // the shekel sign sits outside the isolate, in the RTL flow (after the number in reading)
    expect(bdi?.parentElement?.textContent).toBe("+2,914 ₪");
  });

  it("renders a negative difference with U+2212", () => {
    const { container } = render(<Amount value={-50} signed />);
    expect(container.querySelector("bdi")?.textContent).toBe("−50");
  });
});
