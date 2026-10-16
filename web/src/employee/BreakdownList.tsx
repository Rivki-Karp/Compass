import type { ComparisonView } from "../api/types";
import { Amount } from "../ui/Amount";

/**
 * "מאיפה מגיע ההפרש" as a plain list of the API's lines and total. Stage 4 replaces it with the
 * waterfall and provenance strip; the list stays the accessible fallback.
 */
export function BreakdownList({ view }: { view: ComparisonView }) {
  return (
    <section
      aria-labelledby="breakdown-title"
      className="rounded-card border border-line bg-surface p-6"
    >
      <h2 id="breakdown-title" className="text-[15px] font-semibold text-navy">
        מאיפה מגיע ההפרש
      </h2>
      <ul className="mt-3">
        {view.breakdown.map((line) => (
          <li
            key={line.key}
            className="flex items-center justify-between border-b border-line-soft py-2"
          >
            <span>{line.label}</span>
            <Amount
              value={line.net_effect}
              signed
              currency
              className={`font-semibold ${line.net_effect < 0 ? "text-down" : "text-up"}`}
            />
          </li>
        ))}
        <li className="flex items-center justify-between py-2 font-semibold text-navy">
          <span>סה״כ ההפרש</span>
          <Amount value={view.display_diff} signed currency />
        </li>
      </ul>
    </section>
  );
}
