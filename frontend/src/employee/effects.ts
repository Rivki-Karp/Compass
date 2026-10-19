/**
 * Effects fire once per event, never again for the same event: not when the stream reconnects and
 * replays everything (judges toggle, a new token, a network blip), not when a component remounts
 * (the hero moves between the two layouts). Per channel ("hero", "announce", ...) the memory holds
 * the highest seq whose effect already played; only a higher seq is fresh.
 *
 * The page provides one memory per session; without a provider each component keeps its own
 * (tests, the style guide).
 */

import { createContext, useContext, useEffect, useRef } from "react";

export type EffectsMemory = Record<string, number>;

export const EffectsMemoryContext = createContext<EffectsMemory | null>(null);

/**
 * `isFresh(n)`: whether seq `n` is newer than every seq this channel had played when `seq` first
 * rendered. After the render, `seq` counts as played.
 */
export function useFreshness(channel: string, seq: number): (n: number | null) => boolean {
  const shared = useContext(EffectsMemoryContext);
  const own = useRef<EffectsMemory>({});
  const memory = shared ?? own.current;
  const snapshot = useRef<{ seq: number; before: number } | null>(null);
  if (snapshot.current === null || snapshot.current.seq !== seq) {
    snapshot.current = { seq, before: memory[channel] ?? 0 };
  }
  useEffect(() => {
    memory[channel] = Math.max(memory[channel] ?? 0, seq);
  }, [memory, channel, seq]);
  const before = snapshot.current.before;
  return (n) => n !== null && n > before;
}
