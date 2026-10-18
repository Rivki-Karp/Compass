/**
 * The blocks of an agent reply (round 2, item 5): paragraphs (lines kept), bulleted and numbered
 * lists. Everything else, a table, a heading, a link or HTML included, stays text in a
 * paragraph. ReplyText renders the blocks.
 */

export type Block =
  | { kind: "paragraph"; lines: string[] }
  | { kind: "bullets"; items: string[] }
  | { kind: "numbers"; items: string[] };

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d{1,2}[.)]\s+(.*)$/;

export function parseReply(text: string): Block[] {
  const blocks: Block[] = [];
  for (const line of text.replace(/\r\n?/g, "\n").split("\n")) {
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    const last = blocks.at(-1);
    if (bullet) {
      if (last?.kind === "bullets") last.items.push(bullet[1] ?? "");
      else blocks.push({ kind: "bullets", items: [bullet[1] ?? ""] });
    } else if (numbered) {
      if (last?.kind === "numbers") last.items.push(numbered[1] ?? "");
      else blocks.push({ kind: "numbers", items: [numbered[1] ?? ""] });
    } else if (!line.trim()) {
      blocks.push({ kind: "paragraph", lines: [] }); // a blank line ends the block
    } else if (last?.kind === "paragraph") {
      last.lines.push(line);
    } else {
      blocks.push({ kind: "paragraph", lines: [line] });
    }
  }
  return blocks.filter((b) => (b.kind === "paragraph" ? b.lines.length > 0 : true));
}
