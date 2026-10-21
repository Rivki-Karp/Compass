import {
  DEMO_BARS,
  DEMO_CAR,
  DEMO_CHIPS,
  DEMO_FINAL_DIFF,
  DEMO_PARTICIPATION,
  DEMO_PENDING_DIFF,
} from "./demoValues";

const BAR_TONE = {
  navy: "bg-navy",
  up: "bg-up",
  down: "bg-down",
  royal: "bg-royal",
} as const;

/**
 * The live demo card: it loops between the provisional result ("ממתינה לנציג") and the final one
 * ("סופי"), the bars grow and the source chips show. The figures are the marketing constants of
 * demoValues.ts, not a calculation. One labelled picture for assistive technology, so both states
 * are not read out.
 */
export function DemoCard() {
  return (
    <div
      role="img"
      aria-label={`דוגמה: ${DEMO_CAR}. תוצאה ראשונית ${DEMO_PENDING_DIFF} שקלים, ממתינה לנציג, ואחריה ${DEMO_FINAL_DIFF} שקלים, סופי`}
      className="lp-rise flex flex-col gap-4 rounded-[22px] bg-surface p-7 text-ink shadow-[0_40px_100px_rgba(0,0,0,0.45)] [animation-delay:0.5s]"
    >
      <div aria-hidden="true" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <span className="text-[15px] font-semibold text-muted">
            <bdi>{DEMO_CAR}</bdi>
          </span>
          <span className="relative inline-flex h-[30px] min-w-[132px]">
            <span className="lp-swap-a absolute inset-0 inline-flex items-center justify-center gap-1.5 rounded-chip border border-dashed border-chip-pending-border bg-chip-pending-bg text-[13px] font-semibold text-chip-pending">
              ממתינה לנציג
            </span>
            <span className="lp-swap-b absolute inset-0 inline-flex items-center justify-center gap-1.5 rounded-chip bg-up-bg text-[13px] font-semibold text-up-ink">
              ✓ סופי
            </span>
          </span>
        </div>
        <div className="relative h-[72px]">
          <span className="lp-swap-a absolute inset-0 flex items-baseline gap-2.5 text-[68px] leading-none font-bold text-up opacity-70">
            <bdi>+{DEMO_PENDING_DIFF}</bdi>
            <span className="text-[28px]">₪</span>
            <span className="text-[15px] font-medium text-chip-pending">זמני</span>
          </span>
          <span className="lp-swap-b absolute inset-0 flex items-baseline gap-2.5 text-[68px] leading-none font-bold text-up">
            <bdi>+{DEMO_FINAL_DIFF}</bdi>
            <span className="text-[28px]">₪</span>
            <span className="text-[15px] font-medium text-muted">יותר בנטו, בכל חודש</span>
          </span>
        </div>
        <div className="flex h-[120px] items-end gap-2.5 border-b border-line px-1">
          {DEMO_BARS.map((bar, i) => (
            <div
              key={i}
              className={`lp-bar flex-1 rounded-t-md ${BAR_TONE[bar.tone]}`}
              style={{ height: `${bar.height}%`, animationDelay: `${i * 0.1}s` }}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-2 text-[12px] font-semibold">
          {DEMO_CHIPS.map((chip) => (
            <span key={chip.label} className={`rounded-chip px-2.5 py-1 ${chip.tone}`}>
              {chip.label}
            </span>
          ))}
        </div>
        <span className="text-[13px] text-muted">
          הנציג אישר השתתפות של <bdi>{DEMO_PARTICIPATION}</bdi> ₪, והחישוב התעדכן מעצמו, בשרת, בלי
          המודל.
        </span>
      </div>
    </div>
  );
}
