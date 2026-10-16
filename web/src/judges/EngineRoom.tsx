import type { ReactNode } from "react";
import { SHEKEL } from "../lib/format";
import type { Turn } from "../state/session";
import { Amount } from "../ui/Amount";
import { Icon } from "../ui/icons";
import { engineCards, guardVerdict, sourceLabel, type EngineCard } from "./engine";

const TRIGGER = { employee_turn: "הודעה מהעובד/ת", rep_answer: "תשובת הנציג" } as const;

/**
 * The engine room (brief §4.5): one run at a time, its stats as pills and its events as cards.
 * `selected` null follows the latest run.
 */
export function EngineRoom({
  turns,
  selected,
  onSelect,
}: {
  turns: Turn[];
  selected: number | null;
  onSelect: (index: number | null) => void;
}) {
  const index = selected ?? turns.length - 1;
  const turn = turns[index];
  return (
    <section
      aria-labelledby="engine-title"
      className="flex min-w-0 flex-[999_1_640px] flex-col gap-4 rounded-card bg-engine p-6 text-engine-text"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="engine-title" className="text-[15px] font-semibold">
          חדר המנועים{turn ? ` · תור ${index + 1}` : ""}
        </h2>
        {turns.length > 1 ? (
          <label className="ms-auto flex items-center gap-2 text-[13px] text-engine-muted">
            תור
            <select
              value={selected === null ? "latest" : String(selected)}
              onChange={(e) =>
                onSelect(e.target.value === "latest" ? null : Number(e.target.value))
              }
              className="min-h-11 rounded-control border border-engine-border bg-engine-code px-3 text-engine-text"
            >
              <option value="latest">האחרון ({turns.length})</option>
              {turns.map((t) => (
                <option key={t.index} value={t.index}>
                  {t.index + 1} · {TRIGGER[t.trigger]}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
      {turn ? (
        <>
          <p className="text-[13px] text-engine-muted">
            {TRIGGER[turn.trigger]}
            {turn.finished === null ? " · רץ עכשיו" : ""}
          </p>
          <TurnStats turn={turn} />
          <ol className="flex flex-col gap-3" aria-label="אירועי התור">
            {engineCards(turn).map((card) => (
              <li key={`${card.kind}-${card.seq}`}>
                <Card card={card} />
              </li>
            ))}
          </ol>
        </>
      ) : (
        <p className="text-engine-muted">כאן יופיעו קריאות הכלים ובדיקות השומר של כל תור.</p>
      )}
    </section>
  );
}

function TurnStats({ turn }: { turn: Turn }) {
  const f = turn.finished;
  if (!f || f.usage === undefined) return null; // still running, or no admin fields
  const u = f.usage;
  const pills: [string, ReactNode][] = [
    ["rounds", String(f.rounds ?? "—")],
    ["latency", f.latency_ms == null ? "—" : `${(f.latency_ms / 1000).toFixed(1)}s`],
    ["in", u.input_tokens.toLocaleString("en-US")],
    ["out", u.output_tokens.toLocaleString("en-US")],
    ["cache", u.cache_read_input_tokens.toLocaleString("en-US")],
  ];
  return (
    <ul className="ltr flex flex-wrap gap-2 font-mono text-[12px]" aria-label="נתוני התור">
      {pills.map(([name, value]) => (
        <li key={name} className="rounded-chip border border-engine-border px-3 py-1">
          <span className="text-engine-muted">{name}</span> {value}
        </li>
      ))}
      <li className="rounded-chip border border-engine-tool-border px-3 py-1 text-engine-tool">
        <span className="text-engine-muted">cost</span>{" "}
        {f.cost_usd == null ? "— (demo)" : `$${f.cost_usd}`}
      </li>
    </ul>
  );
}

function Card({ card }: { card: EngineCard }) {
  switch (card.kind) {
    case "tool":
      return (
        <article className="rounded-tile border border-engine-border p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] text-engine-model">המודל קרא לכלי</span>
            <code className="font-mono text-[14px] text-white">{card.name}</code>
            {card.ok === null ? null : card.ok ? (
              <span className="text-engine-tool" aria-label="הצליח">
                ✓
              </span>
            ) : (
              <span className="text-down-bg" aria-label="נכשל">
                ✕
              </span>
            )}
          </div>
          {card.input !== null || card.result !== null ? (
            <details className="mt-2">
              <summary className="cursor-pointer text-[13px] text-engine-muted">קלט ותוצאה</summary>
              <pre
                dir="ltr"
                className="mt-2 max-h-80 overflow-auto rounded-control bg-engine-code p-3 font-mono text-[12px] leading-5 whitespace-pre-wrap"
              >
                {`→ args\n${json(card.input)}\n\n← result\n${json(card.result)}`}
              </pre>
            </details>
          ) : null}
        </article>
      );
    case "comparison": {
      const { view } = card;
      return (
        <article className="rounded-tile border border-engine-tool-border p-4">
          <div className="flex flex-wrap items-center gap-2 text-[13px]">
            <span className="text-engine-tool">
              {card.origin === "server" ? "השרת חישב מחדש · בלי מודל" : "הכלי חישב"}
            </span>
            <span className="text-engine-muted">{view.pending ? "זמני" : "סופי"}</span>
          </div>
          <p className="mt-1 text-white">
            {view.alternative_title}:{" "}
            <span className="font-semibold">
              <Amount value={view.display_diff} signed currency />
            </span>
            {view.today_net !== null && view.alternative_net !== null ? (
              <span className="text-engine-muted">
                {" · נטו "}
                <Amount value={view.today_net} /> ← <Amount value={view.alternative_net} /> {SHEKEL}
              </span>
            ) : null}
          </p>
        </article>
      );
    }
    case "guard":
      return <GuardCard card={card} />;
    case "template":
      return (
        <article className="rounded-tile border border-engine-guard-border p-4">
          <div className="text-[13px] text-engine-guard">נשלחה תשובה מתבנית</div>
          <p className="mt-1 whitespace-pre-wrap text-engine-text">{card.text}</p>
        </article>
      );
    case "rep_answer":
      return (
        <article className="rounded-tile border border-engine-border p-4">
          <div className="text-[13px] text-engine-model">הנציג ענה</div>
          <pre dir="ltr" className="mt-1 font-mono text-[12px] text-white">
            {json(card.values)}
          </pre>
        </article>
      );
    case "error":
      return (
        <article className="rounded-tile border border-down p-4">
          <div className="text-[13px] text-down-bg">שגיאה: {card.error}</div>
          {card.message ? <p className="mt-1 text-engine-muted">{card.message}</p> : null}
        </article>
      );
  }
}

function GuardCard({ card }: { card: Extract<EngineCard, { kind: "guard" }> }) {
  const { guard } = card;
  const sources = guard.sources ?? {};
  const bad = new Set(guard.violations ?? []);
  return (
    <article className="rounded-tile border border-engine-guard-border bg-engine-guard-bg p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Icon name="shield" size={16} className="text-engine-guard" />
        <span className="font-semibold text-engine-guard">שומר המספרים</span>
        <span className="text-[13px] text-engine-text">{guardVerdict(guard)}</span>
      </div>
      {guard.rejected_draft ? (
        <p className="mt-2 text-[13px] text-engine-muted line-through">{guard.rejected_draft}</p>
      ) : null}
      {guard.numbers?.length ? (
        <ul className="mt-2 flex flex-wrap gap-2" aria-label="המספרים בתשובה">
          {guard.numbers.map((n) =>
            bad.has(n) ? (
              <li
                key={n}
                className="rounded-chip border border-down bg-down-bg px-2.5 py-0.5 text-[12px] font-semibold text-down"
              >
                <bdi className="font-mono">{n}</bdi> ✕ אין מקור
              </li>
            ) : (
              <li
                key={n}
                className="rounded-chip border border-engine-guard-border px-2.5 py-0.5 text-[12px] text-engine-text"
              >
                <bdi className="font-mono">{n}</bdi> ✓{" "}
                <span className="font-mono text-engine-guard">{sourceLabel(sources[n] ?? "")}</span>
              </li>
            ),
          )}
        </ul>
      ) : null}
    </article>
  );
}

function json(value: unknown): string {
  return value === null || value === undefined ? "—" : JSON.stringify(value, null, 2);
}
