import type { ChipSource } from "../api/types";
import { CHIP } from "./chips";
import { Icon } from "./icons";

/** A source chip: where an input value came from (see chips.ts). */
export function SourceChip({ source }: { source: ChipSource }) {
  const chip = CHIP[source];
  return (
    <span
      data-source={source}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-chip border px-2.5 py-0.5 text-[12px] leading-5 ${chip.className}`}
    >
      {source === "pending_rep" ? <Icon name="clock" size={13} /> : null}
      {chip.label}
    </span>
  );
}
