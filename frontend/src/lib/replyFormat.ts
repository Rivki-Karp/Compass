/**
 * The blocks of an agent reply (round 2, item 5): paragraphs (lines kept), bulleted and numbered
 * lists. Everything else, a table, a heading, a link or HTML included, stays text in a
 * paragraph. ReplyText renders the blocks.
 */

export type Block =
  | { kind: "paragraph"; lines: string[] }
  | { kind: "bullets"; items: string[] }
  | { kind: "numbers"; items: string[] };

/** A block with where each of its lines (or items) starts in the text that was parsed, so a
 * number's offset in the reply can be found again after the list markers are dropped. */
export type PlacedBlock = Block & { at: number[] };

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d{1,2}[.)]\s+(.*)$/;

/** The blocks, with line offsets. `text` must have no "\r" (callers keep offsets only then). */
export function parseReplyAt(text: string): PlacedBlock[] {
  const blocks: PlacedBlock[] = [];
  let offset = 0;
  for (const line of text.replace(/\r\n?/g, "\n").split("\n")) {
    const lineStart = offset;
    offset += line.length + 1;
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    const last = blocks.at(-1);
    if (bullet) {
      const content = bullet[1] ?? "";
      const at = lineStart + line.length - content.length;
      if (last?.kind === "bullets") {
        last.items.push(content);
        last.at.push(at);
      } else blocks.push({ kind: "bullets", items: [content], at: [at] });
    } else if (numbered) {
      const content = numbered[1] ?? "";
      const at = lineStart + line.length - content.length;
      if (last?.kind === "numbers") {
        last.items.push(content);
        last.at.push(at);
      } else blocks.push({ kind: "numbers", items: [content], at: [at] });
    } else if (!line.trim()) {
      blocks.push({ kind: "paragraph", lines: [], at: [] }); // a blank line ends the block
    } else if (last?.kind === "paragraph") {
      last.lines.push(line);
      last.at.push(lineStart);
    } else {
      blocks.push({ kind: "paragraph", lines: [line], at: [lineStart] });
    }
  }
  return blocks.filter((b) => (b.kind === "paragraph" ? b.lines.length > 0 : true));
}

export function parseReply(text: string): Block[] {
  return parseReplyAt(text).map((placed) => {
    const { at, ...block } = placed;
    void at;
    return block;
  });
}
