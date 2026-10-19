import { describe, expect, it, vi } from "vitest";
import { openStream, SSEParser, type SSEMessage } from "./sse";

describe("SSEParser", () => {
  it("parses id, event and data, skipping heartbeats", () => {
    const parser = new SSEParser();
    const out = parser.push(': ping\r\n\r\nid: 7\r\nevent: tool_call\r\ndata: {"a":1}\r\n\r\n');
    expect(out).toEqual([{ id: "7", event: "tool_call", data: '{"a":1}' }]);
  });

  it("handles chunks split anywhere, including between CR and LF", () => {
    const text = 'id: 1\r\nevent: x\r\ndata: {"t":"שלום"}\r\n\r\nid: 2\r\ndata: b\r\n\r\n';
    for (let cut = 1; cut < text.length; cut++) {
      const parser = new SSEParser();
      const out = [...parser.push(text.slice(0, cut)), ...parser.push(text.slice(cut))];
      expect(out.map((m) => m.id)).toEqual(["1", "2"]);
      expect(out[0]?.data).toBe('{"t":"שלום"}');
    }
  });

  it("joins multi-line data", () => {
    expect(new SSEParser().push("data: a\ndata: b\n\n")[0]?.data).toBe("a\nb");
  });
});

function streamOf(text: string): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

describe("openStream", () => {
  it("sends the token as a header and resumes after the last id", async () => {
    const calls: Headers[] = [];
    const responses = [streamOf("id: 3\ndata: one\n\n"), streamOf("id: 4\ndata: two\n\n")];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      calls.push(new Headers(init?.headers));
      return responses.shift() ?? new Response(null, { status: 401 });
    });
    const messages: SSEMessage[] = [];
    const statuses: string[] = [];
    await new Promise<void>((resolve) => {
      openStream({
        url: "/api/sessions/s/events",
        token: "secret",
        fetchImpl: fetchImpl as unknown as typeof fetch,
        backoff: () => 0,
        onMessage: (m) => messages.push(m),
        onStatus: (s) => {
          statuses.push(s);
          if (s === "unauthorized") resolve();
        },
      });
    });
    expect(messages.map((m) => m.data)).toEqual(["one", "two"]);
    expect(calls[0]?.get("Authorization")).toBe("Bearer secret");
    expect(calls[0]?.has("Last-Event-ID")).toBe(false);
    expect(calls[1]?.get("Last-Event-ID")).toBe("3");
    expect(calls[2]?.get("Last-Event-ID")).toBe("4");
    expect(statuses).toContain("reconnecting");
    for (const [url] of fetchImpl.mock.calls) expect(String(url)).not.toContain("secret");
  });
});
