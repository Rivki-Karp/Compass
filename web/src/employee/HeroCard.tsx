import type { ComparisonView } from "../api/types";
import { SHEKEL, spokenSigned } from "../lib/format";
import type { ComparisonState } from "../state/session";
import { Amount } from "../ui/Amount";
import { Icon } from "../ui/icons";
import { Needle } from "../ui/Needle";
import { SourceChip } from "../ui/SourceChip";

const TONE = { up: "text-up", down: "text-down", flat: "text-ink" } as const;
const CAPTION = {
  up: "יותר בנטו, בכל חודש",
  down: "פחות בנטו, בכל חודש",
  flat: "אין שינוי בנטו",
} as const;

/** What a screen reader hears when a comparison arrives (the region itself never remounts). */
export function HeroAnnouncement({ view }: { view: ComparisonView | null }) {
  return (
    <p aria-live="polite" className="sr-only">
      {view ? `ההפרש עודכן: ${spokenSigned(view.display_diff)}` : ""}
    </p>
  );
}

/**
 * The comparison hero (brief §4.2). The card and the needle stay mounted, so on a new result
 * the needle turns to its new direction; the numbers crossfade in and a royal ring flashes
 * (both keyed by the comparison's seq). Nothing here interpolates digits: every number is the
 * API's.
 */
export function HeroCard({ comparison }: { comparison: ComparisonState }) {
  const view = comparison.view;
  const provisional = view.pending || view.partial;
  return (
    <article
      aria-label="תוצאת ההשוואה"
      className="relative rounded-card border border-line bg-surface p-6"
    >
      <span
        key={`ring-${comparison.seq}`}
        aria-hidden="true"
        className="motion-ring pointer-events-none absolute inset-0 rounded-card"
      />
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-[15px] font-semibold text-navy">
          {view.alternative_title} לעומת היום
        </h2>
        {view.pending ? <SourceChip source="pending_rep" /> : null}
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
          className={`motion-crossfade motion-settle ${provisional ? "opacity-75" : ""}`}
        >
          <div className={`flex items-baseline gap-2 ${TONE[view.direction]}`}>
            <span className="text-[64px] leading-none font-bold">
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

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="self-center rounded-chip bg-chip-pending-bg px-2.5 py-0.5 text-[13px] font-semibold text-chip-pending">
      {children}
    </span>
  );
}

function NetTile({
  label,
  net,
  direction,
  dashed = false,
}: {
  label: string;
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
