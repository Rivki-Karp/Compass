import { Amount } from "./Amount";

/** What a view says in place of its difference: the signed amount, or, while today's car is
 * unknown (display_diff null), the server's note ("חסר הרכב של היום"). */
export function Diff({
  view,
  currency = false,
  className,
}: {
  view: { display_diff: number | null; diff_note: string | null };
  currency?: boolean;
  className?: string;
}) {
  if (view.display_diff === null) return <span className={className}>{view.diff_note ?? "—"}</span>;
  return <Amount value={view.display_diff} signed currency={currency} className={className} />;
}
