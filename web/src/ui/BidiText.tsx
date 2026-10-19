import { Fragment } from "react";
import { splitBidi } from "../lib/bidi";

/**
 * Text from the agent, the employee or the API, with every number and every Latin token isolated
 * in <bdi> (brief §3.6; see lib/bidi.ts). A signed amount keeps its sign in front inside
 * right-to-left text ("+2,914", never "2,914+"), and a car name is one left-to-right unit
 * (<bdi dir="ltr">): "MG4", never "4MG".
 */
export function BidiText({ text }: { text: string }) {
  return (
    <>
      {splitBidi(text).map((part, i) =>
        typeof part === "string" ? (
          <Fragment key={i}>{part}</Fragment>
        ) : "latin" in part ? (
          <bdi key={i} dir="ltr">
            {part.latin}
          </bdi>
        ) : (
          <bdi key={i}>{part.number}</bdi>
        ),
      )}
    </>
  );
}
