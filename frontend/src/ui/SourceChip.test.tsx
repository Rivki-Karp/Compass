import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ChipSource } from "../api/types";
import { Needle } from "./Needle";
import { CHIP } from "./chips";
import { SourceChip } from "./SourceChip";

const ALL: ChipSource[] = [
  "employee_input",
  "occupation",
  "representative",
  "catalog_default",
  "pending_rep",
  "payslip",
  "previous",
];

describe("SourceChip", () => {
  it("has a variant for every source the API sends", () => {
    expect(Object.keys(CHIP).sort()).toEqual([...ALL].sort());
  });

  it.each([
    ["employee_input", "לפי דבריך"],
    ["occupation", "לפי העיסוק"],
    ["representative", "אושר על ידי נציג"],
    ["catalog_default", "ברירת מחדל מהקטלוג"],
    ["pending_rep", "ממתינה לנציג"],
    ["payslip", "לפי התלוש"],
    ["previous", "משיחה קודמת"],
  ] as const)("%s reads %s", (source, label) => {
    render(<SourceChip source={source} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("marks pending as visually distinct: dashed border and a clock icon", () => {
    const { container } = render(<SourceChip source="pending_rep" />);
    const chip = container.querySelector("[data-source=pending_rep]");
    expect(chip?.className).toContain("border-dashed");
    expect(chip?.querySelector("svg[aria-hidden=true]")).not.toBeNull();
  });

  it("only pending has the dashed border and the icon", () => {
    for (const source of ALL.filter((s) => s !== "pending_rep")) {
      const { container, unmount } = render(<SourceChip source={source} />);
      const chip = container.querySelector(`[data-source=${source}]`);
      expect(chip?.className).not.toContain("border-dashed");
      expect(chip?.querySelector("svg")).toBeNull();
      unmount();
    }
  });

  it("shows the representative's chip in bold", () => {
    expect(CHIP.representative.className).toContain("font-semibold");
  });
});

describe("Needle", () => {
  it.each(["up", "down", "flat", "empty"] as const)(
    "renders %s, hidden from screen readers",
    (direction) => {
      const { container } = render(<Needle direction={direction} />);
      const svg = container.querySelector("svg");
      expect(svg?.getAttribute("data-direction")).toBe(direction);
      expect(svg?.getAttribute("aria-hidden")).toBe("true");
    },
  );

  it("points down by rotating the filled half", () => {
    const { container } = render(<Needle direction="down" />);
    expect(container.querySelector("g")?.getAttribute("style")).toContain("rotate(180deg)");
  });
});
