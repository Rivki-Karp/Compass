import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { parseReply } from "../lib/replyFormat";
import { ReplyText } from "./ReplyText";

function html(text: string): HTMLElement {
  const { container } = render(<ReplyText text={text} />);
  return container;
}

describe("ReplyText: a safe subset only", () => {
  it("a markdown table renders as plain text, not HTML", () => {
    const table = "| רכב | הפרש |\n|---|---|\n| MG4 | +1,013 ₪ |\n| EV3 | +747 ₪ |";
    const out = html(table);
    expect(out.querySelector("table, tr, td, th")).toBeNull();
    expect(out.textContent).toContain("| רכב | הפרש |");
    expect(out.textContent).toContain("|---|---|");
    expect(out.querySelectorAll("p")).toHaveLength(1); // one paragraph, lines kept
    expect(out.querySelectorAll("br")).toHaveLength(3);
    const numbers = [...out.querySelectorAll("bdi")].map((b) => b.textContent);
    expect(numbers).toContain("+1,013"); // amounts stay isolated
  });

  it("bold, bulleted and numbered lists, line breaks", () => {
    const out = html(
      "**המובילות:**\n- ויתור: **+2,914 ₪**\n- MG4: +1,013 ₪\n\nואז:\n1. לבחור\n2. לשאול נציג",
    );
    expect(out.querySelector("strong")?.textContent).toBe("המובילות:");
    const bullets = out.querySelectorAll("ul > li");
    expect([...bullets].map((li) => li.textContent)).toEqual(["ויתור: +2,914 ₪", "MG4: +1,013 ₪"]);
    expect(bullets[0]?.querySelector("strong bdi")?.textContent).toBe("+2,914");
    expect(out.querySelectorAll("ol > li")).toHaveLength(2);
  });

  it("no raw HTML, no links, no headings: all stay text", () => {
    const out = html(
      '## כותרת\n<script>alert(1)</script> <b>x</b> <img src=x onerror="alert(1)">\n[קישור](https://evil.example)',
    );
    expect(out.querySelector("script, b, img, a, h1, h2, h3")).toBeNull();
    expect(out.textContent).toContain("## כותרת");
    expect(out.textContent).toContain("<script>alert(1)</script>");
    expect(out.textContent).toContain("[קישור](https://evil.example)");
  });

  it("an unmatched ** stays as typed", () => {
    expect(html("שווי **שימוש").textContent).toBe("שווי **שימוש");
  });

  it("parses lines into blocks", () => {
    expect(parseReply("א\nב\n\n- ג\n- ד\n1. ה")).toEqual([
      { kind: "paragraph", lines: ["א", "ב"] },
      { kind: "bullets", items: ["ג", "ד"] },
      { kind: "numbers", items: ["ה"] },
    ]);
  });
});
