import { Fragment } from "react";
import { splitBidi } from "../lib/bidi";
import type { PlacedSource } from "../lib/numberSources";
import { SourceNumber } from "./NumberSource";

/**
 * Text from the agent, the employee or the API, with every number and every Latin token isolated
 * in <bdi> (brief §3.6; see lib/bidi.ts). A signed amount keeps its sign in front inside
 * right-to-left text ("+2,914", never "2,914+"), and a car name is one left-to-right unit
 * (<bdi dir="ltr">): "MG4", never "4MG".
 *
 * `sources`: the verified numbers of a reply, at their offsets in the text this piece sits in
 * (`base` is where this piece starts). A number that starts where a source starts becomes a
 * button (NumberSource.tsx); every other number is the plain <bdi> it always was.
 */
export function BidiText({
  text,
  sources = [],
  base = 0,
}: {
  text: string;
  sources?: PlacedSource[];
  base?: number;
}) {
  let at = base;
  return (
    <>
      {splitBidi(text).map((part, i) => {
        const start = at;
        const run = typeof part === "string" ? part : "latin" in part ? part.latin : part.number;
        at += run.length;
        if (typeof part === "string") return <Fragment key={i}>{part}</Fragment>;
        if ("latin" in part) {
          return (
            <bdi key={i} dir="ltr">
              {part.latin}
            </bdi>
          );
        }
        // The server (the guard) reads a sign only after a space or a bracket, so in "**+2,092**"
        // or "_+2,092" its span starts at the digit, while this piece, split on its own, starts
        // at the "+": the same number, one sign apart. Same end, start at most one sign earlier.
        const end = start + run.length;
        const signed = /^[+\-−]/.test(run);
        const source = sources.find(
          (s) => s.end === end && (s.start === start || (signed && s.start === start + 1)),
        );
        return (
          <bdi key={i}>
            {source ? <SourceNumber source={source} shown={part.number} /> : part.number}
          </bdi>
        );
      })}
    </>
  );
}
