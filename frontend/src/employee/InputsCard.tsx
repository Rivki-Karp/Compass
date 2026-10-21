import type { ComparisonView } from "../api/types";
import { formatInput } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Icon } from "../ui/icons";
import { SourceChip } from "../ui/SourceChip";
import { BidiText } from "../ui/BidiText";

/** "על מה החישוב מבוסס": every input with its source chip (brief §4.2, invariant 4). */
export function InputsCard({ view }: { view: ComparisonView }) {
  return (
    <section
      aria-labelledby="inputs-title"
      className="rounded-card border border-line bg-surface p-6"
    >
      <h2 id="inputs-title" className="text-[15px] font-semibold text-navy">
        על מה החישוב מבוסס
      </h2>
      <ul className="mt-3 grid gap-x-8 sm:grid-cols-2">
        {view.inputs.map((input) => {
          const pending = input.source === "pending_rep";
          return (
            <li
              key={input.id}
              data-input={input.id}
              className={`flex items-center justify-between gap-3 py-2.5 ${
                pending
                  ? "my-1 rounded-tile border border-dashed border-chip-pending-border px-3"
                  : "border-b border-line-soft"
              }`}
            >
              <span className="min-w-0">
                <span className="text-muted">
                  <BidiText text={input.label} />
                </span>
                {" · "}
                <span className="font-medium text-ink">
                  {input.unit === "ils" && input.value !== null ? (
                    <Amount value={Number(input.value)} currency />
                  ) : (
                    <bdi>{formatInput(input.value, input.unit)}</bdi>
                  )}
                </span>
              </span>
              <SourceChip source={input.source} date={input.previous_from} />
            </li>
          );
        })}
      </ul>
      <p className="mt-4 flex items-center gap-2 text-[13px] text-muted">
        <Icon name="shield" size={15} />
        כל מספר במסך חושב בכלים ונבדק לפני שהוצג.
      </p>
    </section>
  );
}
