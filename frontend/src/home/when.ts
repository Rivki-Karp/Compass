const DAY_MS = 24 * 60 * 60 * 1000;

/** "היום", "אתמול", else day/month: when the conversation last moved. */
export function whenLabel(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const midnight = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((midnight(now) - midnight(then)) / DAY_MS);
  if (days <= 0) return "היום";
  if (days === 1) return "אתמול";
  return `${then.getDate()}/${then.getMonth() + 1}`;
}
