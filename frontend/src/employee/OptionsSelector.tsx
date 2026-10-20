import { useRef, type KeyboardEvent } from "react";
import type { ComparisonView } from "../api/types";
import { formatAmount, spokenDiff } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Diff } from "../ui/Diff";
import type { OptionItem } from "./options";
import { BidiText } from "../ui/BidiText";

const TONE = { up: "text-up", down: "text-down", flat: "text-ink", unknown: "text-muted" } as const;

/** The option as a screen reader hears it: its difference, or its net and the missing car. */
function spokenOption(view: ComparisonView): string {
  if (view.display_diff !== null || view.alternative_net === null) return spokenDiff(view);
  return `נטו ${formatAmount(view.alternative_net)} שקלים, ${spokenDiff(view)}`;
}

/**
 * Every alternative on screen (round 2, item 4), above the hero: name, group and drive, the
 * signed difference and pending/final, best first. A real radio group: one tab stop, the arrow
 * keys move and select (in reading order: in RTL the left arrow is "next"), Home/End, and
 * Enter/Space select. Selecting switches the hero, the waterfall, the provenance strip and the
 * inputs card to that option's view. Scrolls sideways on a narrow screen.
 */
export function OptionsSelector({
  options,
  selected,
  onSelect,
}: {
  options: OptionItem[];
  selected: string;
  onSelect: (key: string) => void;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function move(to: number) {
    const option = options[(to + options.length) % options.length];
    if (!option) return;
    onSelect(option.key);
    const el = refs.current[option.key];
    el?.focus();
    el?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const rtl = getComputedStyle(event.currentTarget).direction === "rtl";
    const next = rtl ? "ArrowLeft" : "ArrowRight";
    const previous = rtl ? "ArrowRight" : "ArrowLeft";
    const key = event.key;
    if (key === next || key === "ArrowDown") move(index + 1);
    else if (key === previous || key === "ArrowUp") move(index - 1);
    else if (key === "Home") move(0);
    else if (key === "End") move(options.length - 1);
    else if (key === "Enter" || key === " ") onSelect(options[index]?.key ?? selected);
    else return;
    event.preventDefault();
  }

  return (
    <section aria-labelledby="options-title" className="flex min-w-0 flex-col gap-2">
      <h2 id="options-title" className="text-[15px] font-semibold text-navy">
        כל החלופות שלך <span className="font-normal text-muted">({options.length})</span>
      </h2>
      <div
        role="radiogroup"
        aria-labelledby="options-title"
        className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2 sm:flex-wrap sm:overflow-visible"
      >
        {options.map((option, index) => {
          const { view } = option.comparison;
          const checked = option.key === selected;
          // no difference yet (today's car unknown): partial, never final
          const state = view.pending ? "זמני" : view.display_diff === null ? "חלקי" : "סופי";
          return (
            <button
              key={option.key}
              ref={(el) => {
                refs.current[option.key] = el;
              }}
              type="button"
              role="radio"
              aria-checked={checked}
              tabIndex={checked ? 0 : -1}
              aria-label={`${view.alternative_title}${view.alternative_details ? `, ${view.alternative_details}` : ""}: ${spokenOption(view)}, ${state}`}
              data-option={option.key}
              onClick={() => onSelect(option.key)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={`flex min-h-11 shrink-0 flex-col items-start gap-1 rounded-tile border px-3 py-2 text-start ${
                checked
                  ? "border-royal bg-surface ring-2 ring-royal"
                  : "border-line bg-surface hover:border-steel"
              }`}
            >
              <span className="text-[14px] font-semibold text-navy">
                <BidiText text={view.alternative_title} />
              </span>
              {view.alternative_details ? (
                <span className="text-[12px] text-muted">
                  <BidiText text={view.alternative_details} />
                </span>
              ) : null}
              {view.display_diff === null && view.alternative_net !== null ? (
                // today's car unknown: the option's own net, and what the difference waits for
                <span className="text-[13px] text-ink">
                  נטו <Amount value={view.alternative_net} currency className="font-semibold" />
                </span>
              ) : null}
              <span className="flex items-center gap-2">
                <span
                  className={
                    view.display_diff === null
                      ? "text-[12px] text-muted"
                      : `text-[15px] font-bold ${TONE[view.direction]}`
                  }
                >
                  <Diff view={view} currency />
                </span>
                <span
                  className={`rounded-chip border px-1.5 text-[11px] ${
                    view.pending || view.display_diff === null
                      ? "border-dashed border-chip-pending-border bg-chip-pending-bg text-chip-pending"
                      : "border-transparent bg-chip-rep-bg text-chip-rep"
                  }`}
                >
                  {state}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
