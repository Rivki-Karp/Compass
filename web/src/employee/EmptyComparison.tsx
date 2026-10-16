import { Needle } from "../ui/Needle";

/** Before any comparison: a quiet card with the needle outline (brief §4.2). */
export function EmptyComparison() {
  return (
    <section className="flex flex-col items-center justify-center gap-4 rounded-card border border-line bg-surface px-6 py-16 text-center">
      <Needle direction="empty" />
      <p className="text-muted">כאן יופיע החישוב ברגע שיהיה מספיק מידע</p>
    </section>
  );
}
