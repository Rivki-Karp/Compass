import { Needle } from "../ui/Needle";

const STEPS = [
  "ספרו על התפקיד, השכר והרכב",
  "הכלים מחשבים את הנטו בדיוק",
  "כל מספר מגיע עם המקור שלו",
] as const;

/** Before any comparison: a calm "how it works" card with the needle outline (brief §4.2).
 * No numbers: nothing has been computed yet. */
export function EmptyComparison() {
  return (
    <section
      aria-labelledby="empty-title"
      className="flex flex-col items-center gap-6 rounded-card border border-line bg-surface px-6 py-12 text-center"
    >
      <Needle direction="empty" />
      <div>
        <h2 id="empty-title" className="text-[15px] font-semibold text-navy">
          איך זה עובד
        </h2>
        <p className="mt-1 text-[13px] text-muted">כאן יופיע החישוב ברגע שיהיה מספיק מידע</p>
      </div>
      <ol className="flex flex-wrap justify-center gap-3">
        {STEPS.map((step, i) => (
          <li
            key={step}
            className="flex w-[200px] flex-col items-center gap-2 rounded-tile border border-line-soft bg-ground px-4 py-4"
          >
            <span
              aria-hidden="true"
              className="flex h-7 w-7 items-center justify-center rounded-full border border-mist text-[13px] font-semibold text-steel"
            >
              {i + 1}
            </span>
            <span className="text-ink">{step}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
