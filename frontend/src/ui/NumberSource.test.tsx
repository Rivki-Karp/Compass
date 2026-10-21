import { render, screen, waitFor, within as inside } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { NumberSource } from "../api/types";
import { originText, placeSources } from "../lib/numberSources";
import { must, views } from "../test/views";
import walkthroughLog from "../test/fixtures/walkthrough.json";
import { displayMinus } from "../lib/format";
import { NumberSourceProvider } from "./NumberSource";
import { ReplyText } from "./ReplyText";

const VIEW = must(views(walkthroughLog)[0]);
const VIEWS = { "21": VIEW };
const REPLY = "הנטו עולה מ-11,000 ₪ ל-13,914 ₪: הפרש של +2,914 ₪ בחודש. שכר הבסיס 18,500 ₪.";

function at(text: string, shown: string): { start: number; end: number } {
  const start = text.indexOf(shown);
  if (start < 0) throw new Error(`no ${shown}`);
  return { start, end: start + shown.length };
}

function source(text: string, shown: string, over: Partial<NumberSource> = {}): NumberSource {
  return {
    ...at(text, shown),
    value: shown.replace(/[,]/g, "").replace("+", "").replace("−", "-"),
    kind: "tool",
    label: "חושב בשרת",
    chip: "computed",
    what: null,
    origin: {
      source: "tool",
      tool: "compare",
      label: "חושב בכלי compare · בשרת, בלי מודל",
      at: null,
    },
    slot: null,
    ref: {},
    ...over,
  };
}

const DIFF = (text: string) =>
  source(text, "+2,914", {
    what: "הפרש בנטו לחודש",
    ref: { comparison_seq: 21, role: "diff" },
  });
const SALARY = (text: string) =>
  source(text, "18,500", {
    kind: "employee",
    label: "לפי דבריך",
    chip: "employee_input",
    what: "שכר בסיס",
    slot: "base_salary",
    origin: {
      source: "employee",
      tool: null,
      label: "לפי דבריך, בהודעה מ־{time}",
      at: "2026-10-21T08:05:00+00:00",
    },
  });

function reply(text: string, sources?: NumberSource[]) {
  return render(
    <NumberSourceProvider views={VIEWS}>
      <p>
        <ReplyText text={text} numberSources={sources} />
      </p>
      <button type="button">elsewhere</button>
    </NumberSourceProvider>,
  );
}

function mobile(matches: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe("a reply's verified numbers", () => {
  it("each recorded number is a labelled button; the other numbers and the text stay as they were", () => {
    const sources = [DIFF(REPLY), SALARY(REPLY)];
    const { container } = reply(REPLY, sources);
    const buttons = screen.getAllByTestId("number-source");
    expect(buttons.map((b) => b.getAttribute("aria-label"))).toEqual([
      "מאיפה המספר +2,914?",
      "מאיפה המספר 18,500?",
    ]);
    expect(buttons[0]).toHaveClass("underline", "decoration-dotted");
    expect(buttons[0]?.tagName).toBe("BUTTON");
    expect(buttons[0]?.closest("bdi")).not.toBeNull(); // still isolated for the bidi algorithm
    expect(container.querySelectorAll("button[data-testid=number-source]")).toHaveLength(2);
    const plain = render(<ReplyText text={REPLY} />).container;
    expect(container.querySelector("p")?.textContent).toBe(plain.textContent);
  });

  it("without sources, or outside a provider, the markup is exactly what it was", () => {
    const bare = render(<ReplyText text={REPLY} />).container.innerHTML;
    const bareProvider = render(
      <NumberSourceProvider views={{}}>
        <ReplyText text={REPLY} />
      </NumberSourceProvider>,
    );
    expect(bareProvider.container.innerHTML).toBe(bare);
    const noProvider = render(<ReplyText text={REPLY} numberSources={[DIFF(REPLY)]} />);
    expect(noProvider.container.innerHTML).toBe(bare); // nothing to open it with: plain
  });

  it("finds the number through list markers, bold and a typed minus with its LRM", () => {
    const text = "**המובילות:**\n- ויתור: **+2,914 ₪**\n2. (\u200E-286 ₪) ועוד 18,500 ₪";
    const sources = [DIFF(text), source(text, "-286"), SALARY(text)];
    reply(text, sources);
    const labels = screen.getAllByTestId("number-source").map((b) => b.textContent);
    expect(labels).toEqual(["+2,914", "−286", "18,500"]);
    expect(placeSources(text, displayMinus(text), sources).map((s) => s.value)).toEqual([
      "2914",
      "-286",
      "18500",
    ]);
  });

  it("an offset that does not land on the number it names is dropped, never moved", () => {
    const wrong = { ...DIFF(REPLY), start: 3, end: 8 };
    const other = { ...DIFF(REPLY), value: "2915" };
    reply(REPLY, [wrong, other]);
    expect(screen.queryAllByTestId("number-source")).toHaveLength(0);
    expect(placeSources("a\r\nb 5", "a\r\nb 5", [source("a\r\nb 5", "5")])).toEqual([]);
  });
});

describe("the popover", () => {
  it("opens on click with the value, what it is, the chip, the origin and the lines it adds up from", async () => {
    reply(REPLY, [DIFF(REPLY)]);
    await userEvent.click(screen.getByTestId("number-source"));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("+2,914 ₪ · הפרש בנטו לחודש");
    expect(inside(dialog).getByText("חושב בשרת")).toBeInTheDocument();
    expect(screen.getByTestId("number-origin")).toHaveTextContent(
      "חושב בכלי compare · בשרת, בלי מודל",
    );
    const lines = inside(dialog).getByRole("list", { name: "מרכיבי ההפרש" });
    expect(inside(lines).getAllByRole("listitem")).toHaveLength(VIEW.breakdown.length);
    expect(lines).toHaveTextContent(must(VIEW.breakdown[0]).label);
    expect(screen.getByTestId("number-source")).toHaveAttribute("aria-expanded", "true");
  });

  it("an employee's number says when they wrote it, in the viewer's time", async () => {
    reply(REPLY, [SALARY(REPLY)]);
    await userEvent.click(screen.getByTestId("number-source"));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("18,500 ₪ · שכר בסיס");
    expect(inside(dialog).getByText("לפי דבריך")).toBeInTheDocument();
    expect(screen.getByTestId("number-origin").textContent).toMatch(
      /לפי דבריך, בהודעה מ־\d\d:\d\d/,
    );
    expect(inside(dialog).queryByRole("list", { name: "מרכיבי ההפרש" })).toBeNull();
  });

  it("opens with Enter and Space, closes with Esc, and focus goes back to the number", async () => {
    const user = userEvent.setup();
    reply(REPLY, [DIFF(REPLY)]);
    const number = screen.getByTestId("number-source");
    number.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(number).toHaveFocus();
    await user.keyboard(" ");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(number).toHaveFocus();
  });

  it("an outside click closes it; on plain content focus goes back to the number, on a control it stays; the number toggles", async () => {
    const user = userEvent.setup();
    reply(REPLY, [DIFF(REPLY)]);
    const number = screen.getByTestId("number-source");
    await user.click(number);
    await user.click(screen.getByText(/שכר הבסיס/).closest("p") as HTMLElement);
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(number).toHaveFocus());
    await user.click(number);
    const elsewhere = screen.getByRole("button", { name: "elsewhere" });
    await user.click(elsewhere);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(elsewhere).toHaveFocus();
    await user.click(number);
    await user.click(number);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("only one is open at a time", async () => {
    const user = userEvent.setup();
    reply(REPLY, [DIFF(REPLY), SALARY(REPLY)]);
    const [first, second] = screen.getAllByTestId("number-source");
    await user.click(must(first));
    await user.click(must(second));
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByRole("dialog")).toHaveTextContent("שכר בסיס");
    expect(first).toHaveAttribute("aria-expanded", "false");
  });

  it("below 700px it is a bottom sheet with a close button", async () => {
    mobile(true);
    reply(REPLY, [DIFF(REPLY)]);
    const number = screen.getByTestId("number-source");
    await userEvent.click(number);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("data-sheet", "true");
    await userEvent.click(inside(dialog).getByRole("button", { name: "סגירה" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(number).toHaveFocus();
  });
});

describe("originText", () => {
  it("fills the time, or drops its clause when there is none", () => {
    expect(originText("אושר על ידי נציג, {time}", "2026-10-21T08:05:00+00:00")).toMatch(
      /^אושר על ידי נציג, \d\d:\d\d$/,
    );
    expect(originText("אושר על ידי נציג, {time}", null)).toBe("אושר על ידי נציג");
    expect(originText("לפי דבריך, בהודעה מ־{time}", null)).toBe("לפי דבריך");
    expect(originText("חושב בשרת", null)).toBe("חושב בשרת");
  });
});
