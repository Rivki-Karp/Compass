import type { ReactNode } from "react";
import { parseReply } from "../lib/replyFormat";
import { NumberText } from "./NumberText";

/**
 * An agent reply, with a small safe subset of Markdown (round 2, item 5): **bold**, bulleted
 * ("- ", "* ", "• ") and numbered ("1. ") lists, and line breaks. Nothing else is interpreted:
 * a table, a heading, a link or HTML stays plain text, exactly as written. Every piece goes
 * through React as text (never innerHTML), so nothing in a reply can become markup, and every
 * number stays isolated in <bdi> (NumberText).
 */

/** **bold** inside one line; an unmatched "**" stays as typed. */
function Inline({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  const bold = /\*\*(.+?)\*\*/g;
  let last = 0;
  for (const match of text.matchAll(bold)) {
    if (match.index > last)
      parts.push(<NumberText key={last} text={text.slice(last, match.index)} />);
    parts.push(
      <strong key={`b${match.index}`} className="font-semibold">
        <NumberText text={match[1] ?? ""} />
      </strong>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(<NumberText key={last} text={text.slice(last)} />);
  return <>{parts}</>;
}

export function ReplyText({ text }: { text: string }) {
  return (
    <>
      {parseReply(text).map((block, i) => {
        if (block.kind === "bullets" || block.kind === "numbers") {
          const List = block.kind === "bullets" ? "ul" : "ol";
          return (
            <List
              key={i}
              className={`my-1 ps-5 ${block.kind === "bullets" ? "list-disc" : "list-decimal"}`}
            >
              {block.items.map((item, j) => (
                <li key={j}>
                  <Inline text={item} />
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
                <Inline text={line} />
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}
