import { Fragment } from "react";

// A number in free text, with its sign only at the start or after a space or bracket, like the
// number guard reads it ("ב-300": the hyphen is a Hebrew prefix, not a minus).
const NUMBER =
  /(?:(?<=^|[\s([])[+\-−])?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?/g;

/**
 * Text from the agent or the employee, with every number isolated in <bdi> (brief §3.6), so a
 * signed amount keeps its sign in front inside right-to-left text: "+2,914", never "2,914+".
 */
export function NumberText({ text }: { text: string }) {
  const parts: (string | { number: string })[] = [];
  let last = 0;
  for (const match of text.matchAll(NUMBER)) {
    const start = match.index;
    if (start > last) parts.push(text.slice(last, start));
    parts.push({ number: match[0] });
    last = start + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return (
    <>
      {parts.map((part, i) =>
        typeof part === "string" ? (
          <Fragment key={i}>{part}</Fragment>
        ) : (
          <bdi key={i}>{part.number}</bdi>
        ),
      )}
    </>
  );
}
