import type { ReactNode } from "react";
import type { NumberSource } from "../api/types";
import { displayMinus } from "../lib/format";
import { placeSources, within, type PlacedSource } from "../lib/numberSources";
import { parseReplyAt } from "../lib/replyFormat";
import { BidiText } from "./BidiText";

/**
 * An agent reply, with a small safe subset of Markdown (round 2, item 5): **bold**, bulleted
 * ("- ", "* ", "• ") and numbered ("1. ") lists, and line breaks. Nothing else is interpreted:
 * a table, a heading, a link or HTML stays plain text, exactly as written. Every piece goes
 * through React as text (never innerHTML), so nothing in a reply can become markup, and every
 * number stays isolated in <bdi> (BidiText). A typed minus before an amount shows as U+2212
 * (displayMinus); display only.
 *
 * `numberSources` (COMPASS_NUMBER_SOURCES=1): the verified numbers of the reply and where each
 * came from. Each one that lands on the number it names becomes a button (NumberSource.tsx);
 * without them, or for any number they do not name, the text is exactly what it always was.
 */

/** **bold** inside one line; an unmatched "**" stays as typed. */
function Inline({
  text,
  base,
  sources,
}: {
  text: string;
  base: number; // where `text` starts in the drawn reply
  sources: PlacedSource[];
}) {
  const parts: ReactNode[] = [];
  const bold = /\*\*(.+?)\*\*/g;
  const piece = (from: number, to: number) => (
    <BidiText
      key={from}
      text={text.slice(from, to)}
      base={base + from}
      sources={within(sources, base + from, base + to)}
    />
  );
  let last = 0;
  for (const match of text.matchAll(bold)) {
    if (match.index > last) parts.push(piece(last, match.index));
    const inner = match.index + 2;
    const content = match[1] ?? "";
    parts.push(
      <strong key={`b${match.index}`} className="font-semibold">
        <BidiText
          text={content}
          base={base + inner}
          sources={within(sources, base + inner, base + inner + content.length)}
        />
      </strong>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(piece(last, text.length));
  return <>{parts}</>;
}

export function ReplyText({
  text,
  numberSources,
}: {
  text: string;
  numberSources?: readonly NumberSource[];
}) {
  const shown = displayMinus(text);
  const sources = placeSources(text, shown, numberSources);
  return (
    <>
      {parseReplyAt(shown).map((block, i) => {
        if (block.kind === "bullets" || block.kind === "numbers") {
          const List = block.kind === "bullets" ? "ul" : "ol";
          return (
            <List
              key={i}
              className={`my-1 ps-5 ${block.kind === "bullets" ? "list-disc" : "list-decimal"}`}
            >
              {block.items.map((item, j) => (
                <li key={j}>
                  <Inline text={item} base={block.at[j] ?? 0} sources={sources} />
                </li>
              ))}
            </List>
          );
        }
        return (
          <p key={i} className="my-1 first:mt-0 last:mb-0">
            {block.lines.map((line, j) => (
              <span key={j}>
                {j > 0 ? <br /> : null}
                <Inline text={line} base={block.at[j] ?? 0} sources={sources} />
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}
