import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import inboxFixture from "../test/fixtures/e001_inbox.json";
import { useRepInbox } from "./useRepInbox";

afterEach(() => vi.unstubAllGlobals());

function sseResponse(body: string) {
  return new Response(body, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

describe("useRepInbox", () => {
  it("without a token: no stream, and no 'unauthorized' that would reject the next token", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useRepInbox(null));
    expect(result.current.connection).toBe("closed");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("a new token starts at 'connecting', not at the previous token's status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) =>
        Promise.resolve(
          new Headers(init.headers).get("Authorization") === "Bearer wrong"
            ? new Response(null, { status: 401 })
            : new Promise<Response>(() => {}), // the good token's stream stays pending
        ),
      ),
    );
    const { result, rerender } = renderHook(({ token }) => useRepInbox(token), {
      initialProps: { token: "wrong" as string | null },
    });
    await waitFor(() => expect(result.current.connection).toBe("unauthorized"));
    rerender({ token: "rep" });
    expect(result.current.connection).toBe("connecting");
  });

  it("opens the inbox stream with the rep bearer and applies each tickets snapshot", async () => {
    const data = JSON.stringify({ tickets: inboxFixture });
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(`event: tickets\ndata: ${data}\n\n`));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useRepInbox("rep"));
    await waitFor(() => expect(result.current.state.tickets).toHaveLength(1));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/tickets/events");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer rep");
    expect(url).not.toContain("rep"); // never in the URL
    act(() => result.current.answered(result.current.state.tickets[0]?.id ?? ""));
    expect(result.current.state.tickets).toEqual([]);
  });
});
