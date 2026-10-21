import type { NumberChip } from "../api/types";
import { formatDayMonth } from "../lib/format";
import { NUMBER_CHIP } from "./chips";
import { Icon } from "./icons";

/** A source chip: where an input value came from (see chips.ts). `label`: the server's word for
 * it (a number in a reply); else the fixed vocabulary of the input chips. */
export function SourceChip({
  source,
  label,
  date,
}: {
  source: NumberChip;
  label?: string;
  /** source "previous": when it was first confirmed, shown as "משיחה קודמת · 20/10" */
  date?: string | null;
}) {
  const chip = NUMBER_CHIP[source];
  return (
    <span
      data-source={source}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-chip border px-2.5 py-0.5 text-[12px] leading-5 ${chip.className}`}
    >
      {source === "pending_rep" ? <Icon name="clock" size={13} /> : null}
      {label ?? chip.label}
      {source === "previous" && date ? (
        <>
          {" · "}
          <bdi>{formatDayMonth(date)}</bdi>
        </>
      ) : null}
    </span>
  );
}
