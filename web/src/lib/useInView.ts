import { useEffect, useState } from "react";

/**
 * Whether the element with `id` is at least partly on screen, below a `topInset` px band (a
 * sticky bar). Watches while `enabled`; `key` re-attaches when the element is replaced. False
 * where IntersectionObserver doesn't exist (tests) or while disabled.
 */
export function useInView(id: string, enabled: boolean, topInset: number, key?: unknown): boolean {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const element = enabled ? document.getElementById(id) : null;
    if (!element || typeof IntersectionObserver !== "function") {
      setInView(false);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setInView(entry?.isIntersecting ?? false),
      { rootMargin: `-${topInset}px 0px 0px 0px` },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [id, enabled, topInset, key]);
  return inView;
}
