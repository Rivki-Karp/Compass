import { describe, expect, it } from "vitest";
import type { ComparisonView } from "../api/types";
import e001Log from "../test/fixtures/e001.json";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { must, views, viewWith } from "../test/views";
import { buildWaterfall, WaterfallInvariantError } from "./buildWaterfall";

const series = (view: ComparisonView) =>
  buildWaterfall(view).steps.map((s) => [s.key, s.value, s.start, s.end]);

const [walkthrough] = views(walkthroughLog);
// E-001's views: pending (the ticket's provisional one, then compare's), then final (the
// server's settle, then compare's): the first pending and the last final
const e001Views = views(e001Log);
const e001Pending = e001Views.find((v) => v.pending);
const e001Final = [...e001Views].reverse().find((v) => !v.pending);

describe("buildWaterfall", () => {
  it("builds the walkthrough series exactly", () => {
    const w = buildWaterfall(must(walkthrough));
    expect(series(must(walkthrough))).toEqual([
      ["maintenance", 1500, 0, 1500],
      ["income_tax", 802, 1500, 2302],
      ["national_insurance", 180, 2302, 2482],
      ["health", 132, 2482, 2614],
      ["participation", 300, 2614, 2914],
    ]);
    expect(w.steps.map((s) => s.label)).toEqual([
      "אחזקת רכב",
      "מס הכנסה",
      "ביטוח לאומי",
      "מס בריאות",
      "השתתפות ברכב",
    ]);
    expect(w.total).toBe(2914);
    expect(w.domain).toEqual([0, 2914]);
    expect(w.defaultKey).toBe("maintenance");
  });

  it("resolves each line's inputs from view.inputs and keeps the API's rules", () => {
    const tax = must(buildWaterfall(must(walkthrough)).steps[1]);
    expect(tax.inputs.map((i) => [i.id, i.value, i.source])).toEqual([
      ["credit_points", "3", "employee_input"],
      ["pension_percent", "6.5", "employee_input"],
      ["base_salary", 18500, "employee_input"],
      ["today_car", "COROLLA CROSS 2025", "employee_input"],
    ]);
    expect(tax.rules.map((r) => r.label)).toEqual([
      "מדרגות מס הכנסה",
      "שווי נקודת זיכוי",
      "זיכוי על הפרשה לפנסיה",
      "שווי שימוש (טבלת רשות המסים)",
    ]);
  });

  it("E-001 pending: four steps to +661", () => {
    const w = buildWaterfall(must(e001Pending));
    expect(series(must(e001Pending))).toEqual([
      ["electric_gross", 440, 0, 440],
      ["income_tax", 160, 440, 600],
      ["national_insurance", 35, 600, 635],
      ["health", 26, 635, 661],
    ]);
    expect(w.total).toBe(661);
    expect(w.defaultKey).toBe("electric_gross");
  });

  it("E-001 after the rep answer: five steps including −50, to +611", () => {
    const w = buildWaterfall(must(e001Final));
    expect(w.steps).toHaveLength(5);
    expect(series(must(e001Final))[4]).toEqual(["participation", -50, 661, 611]);
    expect(w.total).toBe(611);
    expect(w.domain).toEqual([0, 661]);
    const participation = must(w.steps[4]);
    expect(participation.inputs.map((i) => [i.id, i.value, i.source])).toEqual([
      ["today_participation", 300, "employee_input"],
      ["alternative_participation", 350, "representative"],
    ]);
  });

  it("handles a negative total: the domain reaches below zero", () => {
    const w = buildWaterfall(viewWith([["maintenance", 200], ["participation", -900]], -700));
    expect(series(viewWith([["maintenance", 200], ["participation", -900]], -700))).toEqual([
      ["maintenance", 200, 0, 200],
      ["participation", -900, 200, -700],
    ]);
    expect(w.total).toBe(-700);
    expect(w.domain).toEqual([-700, 200]);
    expect(w.defaultKey).toBe("participation");
  });

  it("handles an all-negative series: the domain tops out at zero", () => {
    const w = buildWaterfall(viewWith([["income_tax", -120], ["health", -30]], -150));
    expect(w.domain).toEqual([-150, 0]);
  });

  it("handles a flat difference", () => {
    const w = buildWaterfall(viewWith([["maintenance", 100], ["participation", -100]], 0));
    expect(w.total).toBe(0);
    expect(w.domain).toEqual([0, 100]);
    const empty = buildWaterfall(viewWith([], 0));
    expect(empty.steps).toEqual([]);
    expect(empty.domain).toEqual([0, 0]);
    expect(empty.defaultKey).toBeNull();
  });

  it("throws when the lines do not add up to display_diff", () => {
    expect(() => buildWaterfall(viewWith([["maintenance", 1500]], 1499))).toThrow(
      WaterfallInvariantError,
    );
  });

  it("throws when today + diff != alternative", () => {
    expect(() => buildWaterfall(viewWith([["maintenance", 1500]], 1500, 11000, 12499))).toThrow(
      /today 11000 \+ diff 1500 != alternative 12499/,
    );
  });

  it("skips the nets check when a net is missing (partial)", () => {
    const view = { ...viewWith([["maintenance", 1500]], 1500), alternative_net: null };
    expect(buildWaterfall(view).total).toBe(1500);
  });
});
