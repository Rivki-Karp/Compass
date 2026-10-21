import type { ComparisonView } from "../api/types";
import { formatInput } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Icon } from "../ui/icons";
import { SourceChip } from "../ui/SourceChip";
import type { WaterfallStep } from "./buildWaterfall";
import { BidiText } from "../ui/BidiText";

/**
 * Where the selected number came from (brief §4.3): the line's label and signed value, who
 * computed it (`view.computed_by`: the `compare` tool, or the server with no model), one chip per input (value and source from `view.inputs`), and one chip per
 * rule (the API's label). With the total selected (`step` null) it shows the two nets the
 * difference connects. Everything shown is the API's; nothing is looked up in the frontend.
 */
export function ProvenanceStrip({
  id,
  view,
  step,
  total,
}: {
  id: string;
  view: ComparisonView;
  step: WaterfallStep | null;
  total: number;
}) {
  return (
    <div
      id={id}
      aria-live="polite"
      data-testid="provenance"
      className="mt-4 rounded-tile border border-provenance-border bg-provenance-bg px-4 py-3"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-semibold text-navy">
          {step ? <BidiText text={step.label} /> : "סה״כ ההפרש"}
          {" · "}
          <Amount value={step ? step.value : total} signed currency />
        </span>
        {/* Optional chaining: views stored before Day 5 have no `computed_by`; show nothing. */}
        {view.computed_by?.label ? (
          <span data-testid="computed-by" className="text-[13px] text-muted">
            {view.computed_by.label}
            {view.computed_by.tool ? (
              <>
                {" "}
                <code className="rounded-[6px] bg-tool-chip-bg px-1.5 py-0.5 font-mono text-[12px] text-steel">
                  {view.computed_by.tool}
                </code>
              </>
            ) : null}
          </span>
        ) : null}
      </div>

      {step ? (
        <>
          {step.inputs.length ? (
            <ul aria-label="נתונים" className="mt-2.5 flex flex-wrap gap-2">
              {step.inputs.map((input) => (
                <li
                  key={input.id}
                  data-input={input.id}
                  className="inline-flex items-center gap-2 rounded-chip border border-line bg-surface py-0.5 ps-3 pe-1 text-[13px]"
                >
                  <span>
                    <span className="text-muted">
                      <BidiText text={input.label} />
                    </span>{" "}
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
              ))}
            </ul>
          ) : null}
          {step.rules.length ? (
            <ul aria-label="כללים" className="mt-2 flex flex-wrap gap-2">
              {step.rules.map((rule) => (
                <li
                  key={rule.key}
                  data-rule={rule.key}
                  className="inline-flex items-center gap-1.5 rounded-chip border border-line bg-surface px-3 py-0.5 text-[13px] text-ink"
                >
                  <Icon name="book" size={14} className="text-steel" />
                  <BidiText text={rule.label} />
                  <span className="text-muted">· קובץ הכללים</span>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : view.today_net !== null && view.alternative_net !== null ? (
        <p className="mt-2 text-[13px] text-muted">
          <BidiText text={`היום · ${view.today_title} `} />
          <Amount value={view.today_net} currency className="font-medium text-ink" />
          <BidiText text={` ← ${view.alternative_title} `} />
          <Amount value={view.alternative_net} currency className="font-medium text-ink" />
        </p>
      ) : null}
    </div>
  );
}
