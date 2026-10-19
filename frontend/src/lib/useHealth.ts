import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Health } from "../api/types";

/** GET /api/health once: the LLM mode (demo badge) and the demo scripts (suggestion chips). */
export function useHealth(): Health | null {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => alive && setHealth(h))
      .catch(() => alive && setHealth(null));
    return () => {
      alive = false;
    };
  }, []);
  return health;
}
