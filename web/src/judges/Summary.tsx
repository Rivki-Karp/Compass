import type { ReactNode } from "react";
import type { JudgesStats } from "../api/types";

const STEPS = [
  {
    title: "המודל מציע",
    text: "מבין את השיחה ובוחר כלים. אף פעם לא מחשב כסף.",
    badge: "bg-chip-occupation-bg text-chip-occupation",
  },
  {
    title: "הכלים מחשבים",
    text: "נוסחה דטרמיניסטית, Decimal מדויק, ומקור לכל ערך.",
    badge: "bg-up-bg text-up",
  },
  {
    title: "השומר בודק",
    text: "כל מספר בתשובה חייב להגיע מכלי, מהעובד/ת או מהנציג.",
    badge: "bg-chip-rep-bg text-chip-rep",
  },
] as const;

/** "איך זה עובד" for judges (brief §4.5): who does what, in three numbered steps. */
export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" className="rounded-card border border-line bg-surface p-6">
      <h2 id="how-title" className="text-[15px] font-semibold text-navy">
        איך זה עובד
      </h2>
      <ol className="mt-4 flex flex-col gap-4">
        {STEPS.map((step, i) => (
          <li key={step.title} className="flex items-start gap-3">
            <span
              aria-hidden="true"
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold ${step.badge}`}
            >
              {i + 1}
            </span>
            <div>
              <div className="font-semibold text-ink">{step.title}</div>
              <p className="text-[13px] text-muted">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/**
 * The four stats tiles (brief §4.5, Stage 6), from GET /api/admin/stats: the server reads the
 * committed files; nothing here is hard-coded or computed. `null`: not loaded or unavailable.
 */
export function StatsGrid({ stats }: { stats: JudgesStats | null }) {
  const evals = stats?.evals;
  const spend = stats?.spend;
  const tests = stats?.tests;
  const perRun = stats?.cost_per_conversation;
  return (
    <section aria-label="נתונים" className="grid grid-cols-2 gap-3">
      <Tile
        label="הערכות (evals)"
        value={evals ? `${evals.scenarios_passed}/${evals.scenarios_total}` : null}
        note={
          evals ? (
            <>
              תרחישים · <bdi>{`${evals.runs_passed}/${evals.runs_total}`}</bdi> ריצות ·{" "}
              <bdi className="font-mono">{`${evals.model} · ${evals.effort}`}</bdi>
            </>
          ) : null
        }
      />
      <Tile
        label="הוצאה על הערכות"
        value={spend ? `$${spend.total_usd}` : null}
        note={
          spend ? (
            <>
              {spend.cap_usd ? (
                <>
                  מתוך תקרה של <bdi>{`$${spend.cap_usd}`}</bdi> ·{" "}
                </>
              ) : null}
              {spend.calls} ריצות
            </>
          ) : null
        }
      />
      <Tile
        label="בדיקות"
        value={tests ? `${tests.pytest} + ${tests.vitest}` : null}
        note={
          tests ? (
            <>
              <bdi className="font-mono">pytest + vitest</bdi> · נכון ל-<bdi>{tests.as_of}</bdi>
            </>
          ) : null
        }
      />
      <Tile
        label="עלות לשיחה"
        value={perRun ? `$${perRun.usd}` : null}
        note={perRun ? `ממוצע על ${perRun.runs} ריצות בדוח האחרון` : null}
      />
    </section>
  );
}

function Tile({ label, value, note }: { label: string; value: string | null; note: ReactNode }) {
  return (
    <div className="rounded-tile border border-line bg-surface px-4 py-3">
      <div className="text-[13px] text-muted">{label}</div>
      <div className="mt-1 text-[24px] font-semibold text-navy">
        <bdi>{value ?? "—"}</bdi>
      </div>
      <div className="text-[12px] text-muted">{note ?? "אין נתון"}</div>
    </div>
  );
}
