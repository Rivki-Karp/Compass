import { spokenSigned } from "../lib/format";
import type { ComparisonState } from "../state/session";
import { Amount } from "../ui/Amount";
import { FinalChip, Tag } from "./HeroCard";

const TONE = { up: "text-up", down: "text-down", flat: "text-ink" } as const;

/**
 * The phone summary bar (Day 5 Stage 4): sticky under the header, the alternative's title, the
 * signed difference and the pending/final chip, all from the same `view` as the hero. Tapping it
 * scrolls to the hero card and moves focus there.
 */
export function PhoneBar({ comparison, heroId }: { comparison: ComparisonState; heroId: string }) {
  const { view } = comparison;
  const state = view.pending ? "זמני" : comparison.settled ? "סופי" : null;
  function toHero() {
    const hero = document.getElementById(heroId);
    if (!hero) return;
    const smooth = window.matchMedia?.("(prefers-reduced-motion: no-preference)").matches;
    hero.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
    hero.focus({ preventScroll: true });
  }
  return (
    <button
      type="button"
      data-testid="phone-bar"
      onClick={toHero}
      aria-label={`${view.alternative_title}: ${spokenSigned(view.display_diff)}${state ? `, ${state}` : ""}. מעבר לכרטיס התוצאה`}
      className="sticky top-0 z-20 flex min-h-12 w-full items-center gap-3 border-b border-line bg-surface/95 px-4 py-2 text-start shadow-sm backdrop-blur"
    >
      <span className="min-w-0 flex-1 truncate text-[14px] font-semibold text-navy">
        {view.alternative_title}
      </span>
      <span className={`text-[20px] leading-none font-bold ${TONE[view.direction]}`}>
        <Amount value={view.display_diff} signed currency />
      </span>
      {view.pending ? <Tag>זמני</Tag> : comparison.settled ? <FinalChip /> : null}
    </button>
  );
}
