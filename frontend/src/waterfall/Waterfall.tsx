import { useEffect, useMemo, useRef, useState } from "react";
import type { ComparisonView } from "../api/types";
import { spokenSigned } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Icon } from "../ui/icons";
import { BreakdownTable } from "./BreakdownTable";
import { buildWaterfall, type Waterfall as Series, type WaterfallStep } from "./buildWaterfall";
import { ProvenanceStrip } from "./ProvenanceStrip";

/**
 * "מאיפה מגיע ההפרש" (brief §4.3): the difference only, from zero, as a custom SVG waterfall.
 *
 * Custom SVG rather than Recharts: the chart is six bars, and what matters is exact control of
 * RTL order (first line on the right), real <button> bars with roving focus, the selection
 * outline, and motion that never interpolates numbers; Recharts would fight all four.
 *
 * Each column is a <button> (the hit target is the whole column, wider than the bar) holding a
 * small SVG: the zero line, the bar, and the dashed connectors to its neighbours. Value labels
 * and category labels are HTML so Hebrew wraps and the amounts sit in <bdi>. The columns are
 * laid out right to left by `dir="rtl"`, so the chart reads the same way in any context.
 *
 * Keyboard: Tab enters on the selected bar (the only one with tabIndex 0); ArrowLeft moves to
 * the next line (visually left, in RTL), ArrowRight to the previous one, Home/End to the ends;
 * the selection follows. Enter/Space select as on any button.
 *
 * Pending -> final: bars keep their keys, so a changed bar moves by a height/position
 * transition and a new bar fades in; value labels are keyed by value and swap with a
 * crossfade (no digit is ever interpolated). All motion is in `.motion-*` classes, which do
 * nothing under prefers-reduced-motion.
 */

const PLOT = 200; // px, the bar area
const PAD_TOP = 28; // room for the top value label
const PAD_BOTTOM = 8;
const BAR_X = 22; // % from each side of the column
const MIN_BAR = 2; // px, so a zero step is still a visible mark

type Key = WaterfallStep["key"] | "total";

interface Column {
  key: Key;
  label: string;
  value: number;
  start: number;
  end: number;
  tone: "up" | "down" | "total";
}

const FILL = { up: "var(--color-up)", down: "var(--color-down)", total: "var(--color-navy)" };
const TEXT = { up: "text-up", down: "text-down", total: "text-navy" };

export function Waterfall({ view }: { view: ComparisonView }) {
  const result = useMemo(() => {
    try {
      return { ok: true as const, series: buildWaterfall(view) };
    } catch (error) {
      return { ok: false as const, error };
    }
  }, [view]);

  useEffect(() => {
    if (!result.ok) console.error("waterfall: invariant failed", result.error, view);
  }, [result, view]);

  return (
    <section
      aria-labelledby="waterfall-title"
      className="rounded-card border border-line bg-surface p-6 max-sm:p-4"
    >
      <h2 id="waterfall-title" className="text-[15px] font-semibold text-navy">
        מאיפה מגיע ההפרש
      </h2>
      {result.ok ? (
        <Chart view={view} series={result.series} />
      ) : (
        <p
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-tile border border-down bg-down-bg px-3 py-2 text-[13px] text-down"
        >
          <Icon name="alert" size={16} className="mt-0.5 shrink-0" />
          <span>
            לא ניתן להציג את פירוט ההפרש: הסכומים שהתקבלו אינם מתאימים זה לזה. המספרים בכרטיס
            שלמעלה לא השתנו; נסו לשאול שוב.
          </span>
        </p>
      )}
    </section>
  );
}

function Chart({ view, series }: { view: ComparisonView; series: Series }) {
  const columns: Column[] = [
    ...series.steps.map((step) => ({
      key: step.key,
      label: step.label,
      value: step.value,
      start: step.start,
      end: step.end,
      tone: step.value < 0 ? ("down" as const) : ("up" as const),
    })),
    { key: "total", label: "סה״כ", value: series.total, start: 0, end: series.total, tone: "total" },
  ];

  const [chosen, setChosen] = useState<Key | null>(null);
  const selected: Key =
    chosen !== null && columns.some((c) => c.key === chosen)
      ? chosen
      : (series.defaultKey ?? "total");
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const [low, high] = series.domain;
  const span = high - low || 1; // an all-zero chart still has a zero line
  const y = (value: number) => PAD_TOP + ((high - value) / span) * (PLOT - PAD_TOP - PAD_BOTTOM);

  function move(index: number) {
    const target = columns[Math.max(0, Math.min(columns.length - 1, index))];
    if (!target) return;
    setChosen(target.key);
    buttons.current[columns.indexOf(target)]?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent, index: number) {
    const next = {
      ArrowLeft: index + 1, // RTL: the next line is to the left
      ArrowRight: index - 1,
      Home: 0,
      End: columns.length - 1,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    move(next);
  }

  const step = series.steps.find((s) => s.key === selected) ?? null;
  return (
    <>
      <p className="mt-1 text-[13px] text-muted">לחצו על עמודה כדי לראות את מקור המספר</p>
      <div
        dir="rtl"
        role="group"
        aria-label="פירוט ההפרש לפי שורות"
        className="mt-4 flex items-stretch"
      >
        {columns.map((column, index) => {
          const isSelected = column.key === selected;
          const top = y(Math.max(column.start, column.end));
          const height = Math.max(MIN_BAR, y(Math.min(column.start, column.end)) - top);
          const dimmed = column.tone === "total" && view.pending;
          return (
            <button
              key={column.key}
              ref={(el) => {
                buttons.current[index] = el;
              }}
              type="button"
              data-key={column.key}
              aria-pressed={isSelected}
              aria-controls="provenance-strip"
              aria-label={`${column.label}: ${spokenSigned(column.value)}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => setChosen(column.key)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className="group relative flex min-w-[44px] flex-1 basis-0 flex-col rounded-tile hover:bg-ground"
            >
              <div className="relative w-full" style={{ height: PLOT }}>
                <svg width="100%" height={PLOT} aria-hidden="true" className="block overflow-visible">
                  <line
                    x1="0"
                    x2="100%"
                    y1={y(0)}
                    y2={y(0)}
                    stroke="var(--color-muted)"
                    strokeWidth={1}
                  />
                  {index > 0 ? (
                    <Connector from="100%" to={`${100 - BAR_X}%`} at={y(column.start)} />
                  ) : null}
                  {index < columns.length - 1 ? (
                    <Connector from={`${BAR_X}%`} to="0" at={y(column.end)} />
                  ) : null}
                  <rect
                    data-bar={column.key}
                    x={`${BAR_X}%`}
                    width={`${100 - 2 * BAR_X}%`}
                    y={0}
                    height={height}
                    rx={3}
                    fill={FILL[column.tone]}
                    opacity={dimmed ? 0.75 : 1}
                    className="motion-bar"
                    style={{ transform: `translateY(${top}px)`, height }}
                  />
                </svg>
                {isSelected ? (
                  <span
                    aria-hidden="true"
                    className="motion-bar pointer-events-none absolute rounded-[4px] outline-3 outline-offset-3 outline-royal"
                    style={{ left: `${BAR_X}%`, right: `${BAR_X}%`, top, height }}
                  />
                ) : null}
                <span
                  key={`${column.key}:${column.value}`}
                  className={`motion-crossfade motion-bar absolute inset-x-0 text-center text-[14px] leading-5 font-semibold whitespace-nowrap ${TEXT[column.tone]}`}
                  style={{ top: top - 22 }}
                >
                  <Amount value={column.value} signed />
                </span>
              </div>
              <span
                className={`mt-1.5 px-0.5 text-center text-[12px] leading-4 ${
                  column.tone === "total" ? "font-semibold text-navy" : "text-muted"
                }`}
              >
                {column.label}
              </span>
            </button>
          );
        })}
      </div>
      <ProvenanceStrip id="provenance-strip" view={view} step={step} total={series.total} />
      <details className="mt-3 text-[13px] text-muted">
        <summary className="inline-flex min-h-[44px] cursor-pointer items-center rounded-control px-1">
          הצגה כרשימה
        </summary>
        <BreakdownTable view={view} />
      </details>
    </>
  );
}

function Connector({ from, to, at }: { from: string; to: string; at: number }) {
  return (
    <line
      x1={from}
      x2={to}
      y1={at}
      y2={at}
      stroke="var(--color-mist)"
      strokeWidth={1}
      strokeDasharray="3 3"
    />
  );
}
