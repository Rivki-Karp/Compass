import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ConversationEntry } from "../api/client";
import { resetAuthForTests } from "../auth/authStore";
import { HomeEntry } from "./HomeEntry";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function Opened() {
  return <p>opened {useParams().id}</p>;
}

function stub(list: ConversationEntry[], messages: unknown[] = []) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url.endsWith("/conversations")) return json(list);
      if (url.includes("/sessions/") && !init?.method) return json({ messages });
      if (url.endsWith("/sessions") && init?.method === "POST") return json({ id: "fresh" }, 201);
      return json({}, 404);
    }),
  );
  return calls;
}

const entry = (id: string, status: ConversationEntry["status"]): ConversationEntry => ({
  id,
  title: status === "none" ? "שיחה חדשה" : "ויתור על הרכב",
  updated_at: "2026-10-20T08:00:00+00:00",
  status,
  diff: null,
});

function open() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<HomeEntry />} />
        <Route path="/c/:id" element={<Opened />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => resetAuthForTests({ token: "t", name: "דנה", role: "employee" }));
afterEach(() => {
  vi.unstubAllGlobals();
  resetAuthForTests(null);
});

describe("opening a conversation", () => {
  it("reuses the newest conversation while it is empty", async () => {
    const calls = stub([entry("empty", "none"), entry("old", "final")]);
    open();
    expect(await screen.findByText("opened empty")).toBeInTheDocument();
    expect(calls.some((c) => c.startsWith("POST") && c.endsWith("/sessions"))).toBe(false);
  });

  it("makes a new one when the newest has messages, even without a comparison yet", async () => {
    const calls = stub([entry("talked", "none")], [{ role: "user" }]);
    open();
    expect(await screen.findByText("opened fresh")).toBeInTheDocument();
    expect(calls.filter((c) => c.startsWith("POST") && c.endsWith("/sessions"))).toHaveLength(1);
  });

  it("makes a new one when there is none, once, even though effects run twice", async () => {
    const calls = stub([]);
    open();
    expect(await screen.findByText("opened fresh")).toBeInTheDocument();
    expect(calls.filter((c) => c.startsWith("POST") && c.endsWith("/sessions"))).toHaveLength(1);
  });

  it("offers a retry when the server cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({}, 500)));
    open();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("לא הצלחנו לפתוח שיחה"));
    expect(screen.getByRole("button", { name: "נסו שוב" })).toBeInTheDocument();
  });
});
