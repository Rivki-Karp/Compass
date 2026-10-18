import { useEffect, useRef, useState } from "react";
import type { ComparisonView } from "../api/types";
import { SHEKEL } from "../lib/format";
import type { ComparisonState } from "../state/session";
import { Amount } from "../ui/Amount";
import { Icon } from "../ui/icons";
import { Needle } from "../ui/Needle";
import { SourceChip } from "../ui/SourceChip";
import { useFreshness } from "./effects";
import { announcement, SETTLED_FLASH_MS } from "./settle";

const TONE = { up: "text-up", down: "text-down", flat: "text-ink" } as const;
const CAPTION = {
  up: "יותר בנטו, בכל חודש",
  down: "פחות בנטו, בכל חודש",
  flat: "אין שינוי בנטו",
} as const;

/**
 * The hero's live region. Its text changes only for a fresh comparison, so a replay (reconnect)
 * or a remount (layout change) is never announced again; the page renders it once, outside both
 * layouts.
 */
export function HeroAnnouncement({ comparison }: { comparison: ComparisonState | null }) {
  const seq = comparison?.seq ?? 0;
  const isFresh = useFreshness("announce", seq);
  const fresh = comparison !== null && isFresh(seq);
  const [text, setText] = useState("");
  useEffect(() => {
    if (comparison && fresh) setText(announcement(comparison));
  }, [comparison, fresh]);
  return (
    <p aria-live="polite" className="sr-only">
      {text}
    </p>
  );
}

/** True for SETTLED_FLASH_MS after the comparison that settled a pending one arrives: once
 * (not when a later comparison repeats the settled result, a replay or a remount). */
function useSettledFlash(comparison: ComparisonState, fresh: boolean): boolean {
  const { settledSeq } = comparison;
  const [flashSeq, setFlashSeq] = useState<number | null>(null);
  // Read when settledSeq changes, not a dependency: a later repeat makes it stale, and that
  // must not cancel the running 2 s.
  const freshRef = useRef(fresh);
  freshRef.current = fresh;
  useEffect(() => {
    if (settledSeq === null || !freshRef.current) return;
    setFlashSeq(settledSeq);
    const timer = setTimeout(() => setFlashSeq(null), SETTLED_FLASH_MS);
    return () => clearTimeout(timer);
  }, [settledSeq]);
  return settledSeq !== null && flashSeq === settledSeq;
}

/**
 * The comparison hero (brief §4.2). The card and the needle stay mounted, so on a new result
 * the needle turns to its new direction; the numbers crossfade in and a royal ring flashes
 * (both keyed by the comparison's seq). Nothing here interpolates digits: every number is the
 * API's.
 */
export function HeroCard({
  comparison,
  compact = false,
}: {
  comparison: ComparisonState;
  /** Judges mode's summary column: the number at 52px (brief §4.5). */
  compact?: boolean;
}) {
  const view = comparison.view;
  const provisional = view.pending || view.partial;
  // Motion only for a result the client hasn't shown yet (never on a replay or a remount).
  const isFresh = useFreshness("hero", comparison.seq);
  const fresh = isFresh(comparison.seq);
  const flash = useSettledFlash(comparison, isFresh(comparison.settledSeq));
  return (
    <article
      aria-label="תוצאת ההשוואה"
      className="relative rounded-card border border-line bg-surface p-6"
    >
      <span
        key={`ring-${comparison.seq}`}
        aria-hidden="true"
        className={`pointer-events-none absolute inset-0 rounded-card ${fresh ? "motion-ring" : ""}`}
      />
      {/* final: a 2px `up` border over the card's own for 2 s, no layout shift */}
      <span
        aria-hidden="true"
        data-settled-flash={flash ? "on" : "off"}
        className={`motion-settle pointer-events-none absolute -inset-px rounded-card border-2 border-up ${
          flash ? "opacity-100" : "opacity-0"
        }`}
      />
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-[15px] font-semibold text-navy">
          {view.alternative_title} לעומת היום
        </h2>
        {view.pending ? <SourceChip source="pending_rep" /> : null}
        {comparison.settled ? <FinalChip /> : null}
        {view.group_label ? (
          <span className="ms-auto rounded-chip bg-tool-chip-bg px-3 py-0.5 text-[13px] text-steel">
            {view.group_label}
            {view.group_budget !== null ? (
              <>
                {" · תקציב "}
                <Amount value={view.group_budget} currency />
              </>
            ) : null}
          </span>
        ) : null}
      </div>

      <div className="mt-5 flex items-center gap-5">
        <Needle direction={view.direction} />
        <div
          key={`number-${comparison.seq}`}
          className={`${fresh ? "motion-crossfade" : ""} motion-settle ${provisional ? "opacity-75" : ""}`}
        >
          <div className={`flex items-baseline gap-2 ${TONE[view.direction]}`}>
            <span className={`${compact ? "text-[52px]" : "text-[64px]"} leading-none font-bold`}>
              <Amount value={view.display_diff} signed />
            </span>
            <span className="text-[28px] font-bold">{SHEKEL}</span>
            {view.pending ? <Tag>זמני</Tag> : null}
            {view.partial ? <Tag>חלקי</Tag> : null}
          </div>
          <p className="mt-1 text-muted">{CAPTION[view.direction]}</p>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-stretch gap-3">
        <NetTile label={`היום · ${view.today_title}`} net={view.today_net} />
        <span className="flex items-center text-mist" aria-hidden="true">
          <Icon name="arrowLeft" size={22} />
        </span>
        <NetTile
          label={view.alternative_title}
          details={view.alternative_details}
          net={view.alternative_net}
          direction={view.direction}
          dashed={view.pending}
        />
      </div>

      {view.partial ? (
        <Notice>
          ההפרש חלקי — חסרים: {view.missing.map((m) => m.label).join(", ")}
        </Notice>
      ) : null}
      {view.hypothetical ? (
        <Notice>חישוב היפותטי: לפי הכללים החלופה הזו לא זמינה לך כרגע.</Notice>
      ) : null}
      {view.warnings.length ? (
        <ul className="mt-4 flex flex-col gap-2" aria-label="אזהרות">
          {view.warnings.map((warning) => (
            <li key={warning.code}>
              <Notice inline>{warning.message}</Notice>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function FinalChip() {
  return (
    <span className="inline-flex items-center gap-1 rounded-chip bg-up-bg px-2.5 py-0.5 text-[12px] leading-5 font-semibold text-up">
      <Icon name="check" size={13} />
      סופי
    </span>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="self-center rounded-chip bg-chip-pending-bg px-2.5 py-0.5 text-[13px] font-semibold text-chip-pending">
      {children}
    </span>
  );
}

function NetTile({
  label,
  details = null,
  net,
  direction,
  dashed = false,
}: {
  label: string;
  details?: string | null;
  net: number | null;
  direction?: ComparisonView["direction"];
  dashed?: boolean;
}) {
  const accent =
    direction === "up"
      ? "border-up bg-up-bg/50"
      : direction === "down"
        ? "border-down bg-down-bg/50"
        : "border-line bg-ground";
  return (
    <div
      className={`motion-settle min-w-[180px] flex-1 rounded-tile border px-4 py-3 ${accent} ${dashed ? "border-dashed" : ""}`}
    >
      <div className="text-[13px] text-muted">{label}</div>
      {details ? <div className="text-[12px] text-steel">{details}</div> : null}
      <div className="mt-1 text-[24px] font-semibold text-ink">
        {net === null ? "—" : <Amount value={net} currency />}
      </div>
      <div className="text-[12px] text-muted">נטו בחודש</div>
    </div>
  );
}

function Notice({ children, inline = false }: { children: React.ReactNode; inline?: boolean }) {
  return (
    <p
      className={`flex items-start gap-2 rounded-tile border border-chip-pending-border bg-chip-pending-bg px-3 py-2 text-[13px] text-chip-pending ${inline ? "" : "mt-4"}`}
    >
      <Icon name="alert" size={16} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}
