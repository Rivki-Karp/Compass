import type { ComparisonState } from "../state/session";

/** Below this width the layout is one column and the hero scrolls away under the chat. */
export const PHONE_QUERY = "(max-width: 699.98px)";

/** The phone summary bar shows on a phone, once there is a comparison, outside judges mode. */
export function phoneBarVisible({
  narrow,
  comparison,
  judges,
}: {
  narrow: boolean;
  comparison: ComparisonState | null;
  judges: boolean;
}): boolean {
  return narrow && comparison !== null && !judges;
}
