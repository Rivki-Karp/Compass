import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ConversationEntry } from "../api/client";

export interface UseConversations {
  /** null until the first answer. */
  items: ConversationEntry[] | null;
  failed: boolean;
  reload: () => void;
}

/**
 * The user's own conversations (GET /conversations). Reloaded when asked and whenever `watch`
 * changes (the open conversation got a new event: its title or diff may have), a little later so
 * a burst of events is one request.
 */
export function useConversations(enabled: boolean, watch: unknown): UseConversations {
  const [items, setItems] = useState<ConversationEntry[] | null>(null);
  const [failed, setFailed] = useState(false);
  const alive = useRef(true);

  const load = useCallback(() => {
    api
      .conversations()
      .then((list) => {
        if (!alive.current) return;
        setItems(list);
        setFailed(false);
      })
      .catch(() => alive.current && setFailed(true));
  }, []);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const timer = setTimeout(load, items === null ? 0 : 700);
    return () => clearTimeout(timer);
    // `items` only decides the first delay; reloading on it would loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, watch, load]);

  return { items, failed, reload: load };
}
