import type { ComparisonView } from "../api/types";
import { Amount } from "../ui/Amount";

/** The waterfall's lines as a plain table: the chart's text view (under "הצגה כרשימה"). */
export function BreakdownTable({ view }: { view: ComparisonView }) {
  return (
    <table className="mt-2 w-full text-[14px] text-ink">
      <caption className="sr-only">פירוט ההפרש</caption>
      <tbody>
        {view.breakdown.map((line) => (
          <tr key={line.key} className="border-b border-line-soft">
            <th scope="row" className="py-2 text-start font-normal">
              {line.label}
            </th>
            <td className="py-2 text-end">
              <Amount
                value={line.net_effect}
                signed
                currency
                className={`font-semibold ${line.net_effect < 0 ? "text-down" : "text-up"}`}
              />
            </td>
          </tr>
        ))}
        <tr className="font-semibold text-navy">
          <th scope="row" className="py-2 text-start">
            סה״כ ההפרש
          </th>
          <td className="py-2 text-end">
            <Amount value={view.display_diff} signed currency />
          </td>
        </tr>
      </tbody>
    </table>
  );
}
