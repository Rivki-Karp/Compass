/**
 * Server-sent events over fetch, so a stream can send `Authorization` (judges mode, the rep
 * inbox) and `Last-Event-ID` as headers. Browser EventSource can't set headers, and tokens never
 * go in a URL. Reconnects with backoff and resumes after the last id it saw; a 401/403/404 stops
 * (retrying won't help).
 */

export interface SSEMessage {
  id: string | null;
  event: string;
  data: string;
}

/** Incremental text/event-stream parser: push chunks, get complete messages. */
export class SSEParser {
  private buffer = "";
  private id: string | null = null;
  private event = "";
  private data: string[] = [];

  push(chunk: string): SSEMessage[] {
    this.buffer += chunk;
    const out: SSEMessage[] = [];
    let newline: number;
    while ((newline = this.buffer.search(/\r\n|\r|\n/)) >= 0) {
      // A chunk may end between "\r" and "\n" (sse-starlette uses CRLF): wait for the rest.
      if (this.buffer[newline] === "\r" && newline === this.buffer.length - 1) break;
      const line = this.buffer.slice(0, newline);
      const width = this.buffer.startsWith("\r\n", newline) ? 2 : 1;
      this.buffer = this.buffer.slice(newline + width);
      if (line === "") {
        if (this.data.length) {
          out.push({ id: this.id, event: this.event || "message", data: this.data.join("\n") });
        }
        this.event = "";
        this.data = [];
        continue;
      }
      if (line.startsWith(":")) continue; // comment (heartbeat)
      const colon = line.indexOf(":");
      const field = colon < 0 ? line : line.slice(0, colon);
      let value = colon < 0 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "data") this.data.push(value);
      else if (field === "event") this.event = value;
      else if (field === "id") this.id = value;
    }
    return out;
  }
}

/** "gone": 404, the resource doesn't exist (any more); "closed": closed by the caller. */
export type StreamStatus =
  | "connecting"
  | "open"
  | "reconnecting"
  | "unauthorized"
  | "gone"
  | "closed";

export interface StreamOptions {
  url: string;
  token?: string | null;
  lastEventId?: string | null;
  onMessage: (message: SSEMessage) => void;
  onStatus?: (status: StreamStatus) => void;
  fetchImpl?: typeof fetch;
  /** Backoff in ms for attempt n (0-based). */
  backoff?: (attempt: number) => number;
}

const defaultBackoff = (attempt: number) => Math.min(1000 * 2 ** attempt, 10_000);

/** Open a stream; returns a function that closes it for good. */
export function openStream(options: StreamOptions): () => void {
  const fetchImpl = options.fetchImpl ?? fetch;
  const backoff = options.backoff ?? defaultBackoff;
  let lastId = options.lastEventId ?? null;
  let closed = false;
  let attempt = 0;
  let controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const status = (s: StreamStatus) => options.onStatus?.(s);

  async function connect(): Promise<void> {
    controller = new AbortController();
    const headers: Record<string, string> = { Accept: "text/event-stream" };
    if (options.token) headers.Authorization = `Bearer ${options.token}`;
    if (lastId !== null) headers["Last-Event-ID"] = lastId;
    status(attempt === 0 ? "connecting" : "reconnecting");
    try {
      const response = await fetchImpl(options.url, { headers, signal: controller.signal });
      if ([401, 403, 404].includes(response.status)) {
        closed = true;
        status(response.status === 404 ? "gone" : "unauthorized");
        return;
      }
      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
      status("open");
      attempt = 0;
      const parser = new SSEParser();
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const message of parser.push(value)) {
          if (message.id !== null) lastId = message.id;
          options.onMessage(message);
        }
      }
    } catch (error) {
      if (closed) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
    }
    if (closed) return;
    status("reconnecting");
    timer = setTimeout(() => void connect(), backoff(attempt++));
  }

  void connect();
  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
    controller?.abort();
    status("closed");
  };
}
