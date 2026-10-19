import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ComparisonView } from "../api/types";
import e001Log from "../test/fixtures/e001.json";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { must, views, viewWith } from "../test/views";
import { Waterfall } from "./Waterfall";

const [walkthrough] = views(walkthroughLog);
// E-001's views: pending (the ticket's provisional one, then compare's), then final (the
// server's settle, then compare's): the first pending and the last final
const e001Views = views(e001Log);
const e001Pending = e001Views.find((v) => v.pending);
const e001Final = [...e001Views].reverse().find((v) => !v.pending);

const bars = () => within(screen.getByRole("group", { name: "פירוט ההפרש לפי שורות" })).getAllByRole("button");
const selectedKey = () =>
  bars().find((b) => b.getAttribute("aria-pressed") === "true")?.dataset.key;
const strip = () => screen.getByTestId("provenance");

describe("Waterfall", () => {
  it("draws one button per line plus the total, in API order, inside an RTL row", () => {
    render(<Waterfall view={must(walkthrough)} />);
    expect(screen.getByRole("group", { name: "פירוט ההפרש לפי שורות" })).toHaveAttribute("dir", "rtl");
    expect(bars().map((b) => b.dataset.key)).toEqual([
      "maintenance",
      "income_tax",
      "national_insurance",
      "health",
      "participation",
      "total",
    ]);
    expect(bars().map((b) => b.textContent)).toEqual([
      "+1,500אחזקת רכב",
      "+802מס הכנסה",
      "+180ביטוח לאומי",
      "+132מס בריאות",
      "+300השתתפות ברכב",
      "+2,914סה״כ",
    ]);
    expect(document.querySelector('[data-bar="total"]')).toHaveAttribute(
      "fill",
      "var(--color-navy)",
    );
  });

  it("selects the largest step by default and shows its provenance", () => {
    render(<Waterfall view={must(walkthrough)} />);
    expect(selectedKey()).toBe("maintenance");
    expect(strip()).toHaveTextContent("אחזקת רכב · +1,500 ₪");
  });

  it("shows the 802 line's inputs with their sources and its rules", () => {
    render(<Waterfall view={must(walkthrough)} />);
    fireEvent.click(must(bars()[1]));
    expect(selectedKey()).toBe("income_tax");
    expect(strip()).toHaveTextContent("מס הכנסה · +802 ₪");
    expect(strip()).toHaveTextContent("חושב בכלי compare");
    const inputs = within(strip()).getByRole("list", { name: "נתונים" });
    const chips = within(inputs).getAllByRole("listitem");
    expect(chips.map((c) => c.dataset.input)).toEqual([
      "credit_points",
      "pension_percent",
      "base_salary",
      "today_car",
    ]);
    expect(must(chips[0])).toHaveTextContent("נקודות זיכוי 3לפי דבריך");
    expect(must(chips[1])).toHaveTextContent("הפרשת עובד לפנסיה 6.5%לפי דבריך");
    expect(must(chips[2])).toHaveTextContent("שכר בסיס 18,500 ₪לפי דבריך");
    const rules = within(strip()).getByRole("list", { name: "כללים" });
    expect(within(rules).getAllByRole("listitem")).toHaveLength(4);
    expect(rules).toHaveTextContent("מדרגות מס הכנסה");
  });

  it("moves through the bars with the keyboard in RTL order", async () => {
    const user = userEvent.setup();
    render(<Waterfall view={must(walkthrough)} />);
    expect(bars().filter((b) => b.tabIndex === 0)).toHaveLength(1);

    await user.tab();
    expect(document.activeElement).toBe(bars()[0]);

    const visited = [selectedKey()];
    for (let i = 0; i < 6; i++) {
      await user.keyboard("{ArrowLeft}"); // RTL: the next line is to the left
      visited.push(selectedKey());
    }
    expect(visited).toEqual([
      "maintenance",
      "income_tax",
      "national_insurance",
      "health",
      "participation",
      "total",
      "total", // stops at the end
    ]);
    expect(document.activeElement).toBe(bars()[5]);
    expect(strip()).toHaveTextContent("סה״כ ההפרש · +2,914 ₪");

    await user.keyboard("{ArrowRight}");
    expect(selectedKey()).toBe("participation");
    expect(document.activeElement).toBe(bars()[4]);
    await user.keyboard("{Home}");
    expect(selectedKey()).toBe("maintenance");
    await user.keyboard("{End}");
    expect(selectedKey()).toBe("total");
    expect(bars().filter((b) => b.tabIndex === 0)).toEqual([bars()[5]]);
  });

  it("selects with Enter and Space like any button", async () => {
    const user = userEvent.setup();
    render(<Waterfall view={must(walkthrough)} />);
    must(bars()[3]).focus();
    await user.keyboard("{Enter}");
    expect(selectedKey()).toBe("health");
    must(bars()[2]).focus();
    await user.keyboard(" ");
    expect(selectedKey()).toBe("national_insurance");
  });

  it("swaps E-001 pending to final: the −50 step appears and the total label swaps", () => {
    const { rerender } = render(<Waterfall view={must(e001Pending)} />);
    expect(bars()).toHaveLength(5);
    expect(within(must(bars()[4])).getByText("+661")).toBeInTheDocument();
    expect(document.querySelector('[data-bar="total"]')).toHaveAttribute("opacity", "0.75");

    rerender(<Waterfall view={must(e001Final)} />);
    expect(bars()).toHaveLength(6);
    expect(document.body.textContent).not.toContain("+661");
    expect(within(must(bars()[5])).getByText("+611")).toBeInTheDocument();
    expect(within(must(bars()[4])).getByText("−50")).toBeInTheDocument();
    expect(document.querySelector('[data-bar="total"]')).toHaveAttribute("opacity", "1");

    fireEvent.click(must(bars()[4]));
    expect(strip()).toHaveTextContent("השתתפות ברכב · −50 ₪");
    expect(strip()).toHaveTextContent("השתתפות בחלופה 350 ₪אושר על ידי נציג");
  });

  it("says the server computed E-001's provisional comparison, with no tool chip", () => {
    // the first E-001 view is the provisional comparison the server made when the ticket opened
    const provisional = must(e001Views[0]);
    expect(provisional.computed_by.origin).toBe("server");
    render(<Waterfall view={provisional} />);
    expect(screen.getByTestId("computed-by")).toHaveTextContent(/^חושב מחדש בשרת · בלי מודל$/);
    expect(within(strip()).queryByText("compare")).toBeNull();
    expect(strip()).not.toHaveTextContent("חושב בכלי");
  });

  it("renders the computed-by label it receives, as is", () => {
    const base = must(walkthrough);
    const { rerender } = render(
      <Waterfall view={{ ...base, computed_by: { origin: "server", label: "תווית מהשרת", tool: null } }} />,
    );
    expect(screen.getByTestId("computed-by")).toHaveTextContent(/^תווית מהשרת$/);

    rerender(<Waterfall view={{ ...base, computed_by: { origin: "tool", label: "כלי", tool: "x_tool" } }} />);
    expect(screen.getByTestId("computed-by")).toHaveTextContent(/^כלי x_tool$/);
    expect(within(strip()).getByText("x_tool").tagName).toBe("CODE");
  });

  it("shows no computed-by line for a view stored before it existed", () => {
    const legacy: Partial<ComparisonView> = { ...must(walkthrough) };
    delete legacy.computed_by;
    render(<Waterfall view={legacy as ComparisonView} />);
    expect(screen.queryByTestId("computed-by")).toBeNull();
    expect(strip()).toHaveTextContent("אחזקת רכב · +1,500 ₪");
  });

  it("draws a negative total below the zero line", () => {
    render(<Waterfall view={viewWith([["maintenance", 200], ["participation", -900]], -700)} />);
    expect(bars().map((b) => b.textContent)).toEqual([
      "+200label:maintenance",
      "−900label:participation",
      "−700סה״כ",
    ]);
    expect(document.querySelector('[data-bar="participation"]')).toHaveAttribute(
      "fill",
      "var(--color-down)",
    );
  });

  it("draws a flat, empty difference without NaN", () => {
    const { container } = render(<Waterfall view={viewWith([], 0)} />);
    expect(bars().map((b) => b.dataset.key)).toEqual(["total"]);
    expect(selectedKey()).toBe("total");
    expect(container.innerHTML).not.toContain("NaN");
  });

  it("shows an error state and logs the payload when an invariant fails", () => {
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    const broken = viewWith([["maintenance", 1500]], 1499);
    render(<Waterfall view={broken} />);
    expect(screen.getByRole("alert")).toHaveTextContent("לא ניתן להציג את פירוט ההפרש");
    expect(screen.queryByRole("group", { name: "פירוט ההפרש לפי שורות" })).toBeNull();
    expect(screen.queryByText("+1,500")).toBeNull();
    expect(log).toHaveBeenCalledWith(
      "waterfall: invariant failed",
      expect.any(Error),
      broken,
    );
    log.mockRestore();
  });
});
