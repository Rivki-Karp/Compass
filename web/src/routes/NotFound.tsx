import { Link } from "react-router-dom";
import { Needle } from "../ui/Needle";
import { Header } from "../ui/Header";

/** Any path the UI doesn't know (in the production build, /__styleguide too): never blank. */
export function NotFound() {
  return (
    <div className="min-h-screen bg-ground">
      <Header heading={false} />
      <main className="px-8 py-12 max-sm:px-4">
        <section
          aria-labelledby="not-found-title"
          className="mx-auto flex max-w-[480px] flex-col items-center gap-4 rounded-card border border-line bg-surface px-6 py-12 text-center"
        >
          <Needle direction="empty" />
          <h1 id="not-found-title" className="text-[22px] font-bold text-navy">
            הדף לא נמצא
          </h1>
          <p className="text-muted">הכתובת הזו לא קיימת במערכת.</p>
          <Link
            to="/"
            className="inline-flex min-h-11 items-center rounded-control bg-royal px-4 font-medium text-white hover:bg-navy"
          >
            לדף הבית
          </Link>
        </section>
      </main>
    </div>
  );
}
