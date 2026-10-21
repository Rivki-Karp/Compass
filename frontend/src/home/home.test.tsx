import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdminPage } from "../admin/AdminPage";
import { AppRoutes } from "../App";
import type { AdminUser, ConversationEntry } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import { getAuth, resetAuthForTests, type AuthUser } from "../auth/authStore";
import { ConversationSidebar } from "./ConversationSidebar";
import { whenLabel } from "./when";

const json = (body: unknown, status = 200) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: status === 204 ? {} : { "content-type": "application/json" },
  });

const HEALTH_ON = { ok: true, llm: "none", demo_scripts: null, dev_tools: false, accounts: true };
const USER = (role: AuthUser["role"]): AuthUser => ({ token: "tok", name: "דנה לוי", role });

type Route = (url: string, init?: RequestInit) => Response | undefined;

function stubApi(...routes: Route[]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({
        url,
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      });
      if (url.endsWith("/health")) return json(HEALTH_ON);
      for (const route of routes) {
        const response = route(url, init);
        if (response) return response;
      }
      return json({ detail: "not stubbed" }, 404);
    }),
  );
  return calls;
}

beforeEach(() => resetAuthForTests(null));
afterEach(() => {
  vi.unstubAllGlobals();
  resetAuthForTests(null);
  sessionStorage.clear();
});

const ENTRIES: ConversationEntry[] = [
  { id: "a", title: "קורולה קרוס מול ATTO 3", updated_at: new Date().toISOString(), status: "final", diff: 611 },
  { id: "b", title: "ויתור על הרכב", updated_at: "2020-01-02T10:00:00+00:00", status: "final", diff: 2914 },
  { id: "c", title: "כל החלופות בקבוצה ב׳", updated_at: "2020-01-02T10:00:00+00:00", status: "pending", diff: null },
];

describe("when", () => {
  it("says today, yesterday, then the date", () => {
    const now = new Date(2026, 9, 20, 12, 0);
    expect(whenLabel(new Date(2026, 9, 20, 8).toISOString(), now)).toBe("היום");
    expect(whenLabel(new Date(2026, 9, 19, 23).toISOString(), now)).toBe("אתמול");
    expect(whenLabel(new Date(2026, 9, 18, 9).toISOString(), now)).toBe("18/10");
  });
});

describe("the conversation list", () => {
  function renderSidebar(onDelete = vi.fn().mockResolvedValue(undefined)) {
    render(
      <MemoryRouter>
        <ConversationSidebar items={ENTRIES} failed={false} currentId="a" onDelete={onDelete} />
      </MemoryRouter>,
    );
    return onDelete;
  }

  it("lists each conversation with its title, diff and state, and says only you see them", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: "שיחה חדשה" })).toHaveAttribute("href", "/new");
    const nav = screen.getByRole("complementary", { name: "השיחות שלי" });
    const first = within(nav).getByRole("link", { name: /קורולה קרוס מול/ });
    expect(first).toHaveAttribute("href", "/c/a");
    expect(first).toHaveAttribute("aria-current", "page");
    expect(first).toHaveTextContent("+611");
    expect(first).toHaveTextContent("סופי");
    expect(within(nav).getByRole("link", { name: /ויתור על הרכב/ })).toHaveTextContent("+2,914");
    expect(within(nav).getByRole("link", { name: /כל החלופות/ })).toHaveTextContent("ממתינה לנציג");
    expect(screen.getByText("רק את/ה רואה את השיחות האלה.")).toBeInTheDocument();
  });

  it("deletes only after a confirmation, and cancel deletes nothing", async () => {
    const user = userEvent.setup();
    const onDelete = renderSidebar();
    await user.click(screen.getByRole("button", { name: "מחיקת שיחה: ויתור על הרכב" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("למחוק את השיחה?");
    await user.click(within(dialog).getByRole("button", { name: "ביטול" }));
    expect(onDelete).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "מחיקת שיחה: ויתור על הרכב" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "מחיקה" }));
    expect(onDelete).toHaveBeenCalledWith("b");
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });

  it("keeps the dialog and says so when the delete fails", async () => {
    const user = userEvent.setup();
    renderSidebar(vi.fn().mockRejectedValue(new Error("no")));
    await user.click(screen.getByRole("button", { name: "מחיקת שיחה: ויתור על הרכב" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "מחיקה" }));
    expect(await screen.findByText("המחיקה נכשלה. נסו שוב.")).toBeInTheDocument();
  });
});

const USERS: AdminUser[] = [
  { id: "u1", email: "dana@example.com", name: "דנה", role: "employee", status: "active", created_at: "2026-10-01T08:00:00+00:00", last_login_at: null },
  { id: "u2", email: "admin@example.com", name: "מנהלת", role: "admin", status: "active", created_at: "2026-10-01T08:00:00+00:00", last_login_at: "2026-10-20T08:00:00+00:00" },
];

function renderAdmin() {
  resetAuthForTests(USER("admin"));
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <AuthProvider>
        <AdminPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("the admin page", () => {
  const listUsers: Route = (url, init) =>
    url.endsWith("/admin/users") && (init?.method ?? "GET") === "GET" ? json(USERS) : undefined;

  it("shows users with access fields only and no way into a conversation", async () => {
    stubApi(listUsers, (url) => (url.endsWith("/auth/me") ? json({ name: "דנה לוי", role: "admin" }) : undefined));
    renderAdmin();
    const table = await screen.findByRole("table", { name: "משתמשים" });
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "שם", "מייל", "תפקיד", "סטטוס", "נוצר", "כניסה אחרונה", "פעולות",
    ]);
    expect(within(table).getByText("dana@example.com")).toBeInTheDocument();
    const links = screen.queryAllByRole("link").map((a) => a.getAttribute("href"));
    expect(links.filter((href) => href?.startsWith("/c/") || href?.includes("session"))).toEqual([]);
  });

  it("invites: the code is shown once, with a copy button", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    const calls = stubApi(
      listUsers,
      (url, init) =>
        url.endsWith("/admin/invites") && init?.method === "POST"
          ? json({ code: "ABCDE-FGHJK", email: "new@example.com", role: "rep", expires_at: "2026-10-22T08:00:00+00:00" }, 201)
          : undefined,
    );
    renderAdmin();
    await screen.findByRole("table", { name: "משתמשים" });
    await user.type(screen.getByLabelText("מייל"), "new@example.com");
    await user.selectOptions(screen.getByLabelText("תפקיד"), "rep");
    await user.click(screen.getByRole("button", { name: "יצירת קוד הזמנה" }));
    const dialog = await screen.findByRole("dialog", { name: "קוד הזמנה" });
    expect(within(dialog).getByLabelText("הקוד")).toHaveTextContent("ABCDE-FGHJK");
    expect(dialog).toHaveTextContent("הקוד יוצג פעם אחת בלבד");
    await user.click(within(dialog).getByRole("button", { name: "העתקה" }));
    expect(writeText).toHaveBeenCalledWith("ABCDE-FGHJK");
    expect(calls.find((c) => c.url.endsWith("/admin/invites"))?.body).toEqual({ email: "new@example.com", role: "rep" });

    await user.click(within(dialog).getByRole("button", { name: "סגירה" }));
    await waitFor(() => expect(screen.queryByText("ABCDE-FGHJK")).toBeNull()); // gone for good
  });

  it("says why an existing user cannot be invited again", async () => {
    const user = userEvent.setup();
    stubApi(listUsers, (url, init) =>
      url.endsWith("/admin/invites") && init?.method === "POST"
        ? json({ detail: "כבר קיים משתמש עם המייל הזה. כדי להזמין מחדש, מחקו אותו קודם." }, 409)
        : undefined,
    );
    renderAdmin();
    await screen.findByRole("table", { name: "משתמשים" });
    await user.type(screen.getByLabelText("מייל"), "dana@example.com");
    await user.click(screen.getByRole("button", { name: "יצירת קוד הזמנה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("מחקו אותו קודם");
  });

  it("changes a role and a status, and shows a guard's refusal", async () => {
    const user = userEvent.setup();
    const calls = stubApi(listUsers, (url, init) => {
      if (init?.method !== "PATCH") return undefined;
      const body = JSON.parse(String(init.body)) as { role?: string; status?: string };
      return url.endsWith("/u2")
        ? json({ detail: "אי אפשר לשנות, להשבית או למחוק את החשבון של עצמך" }, 409)
        : json({ ...USERS[0], ...body });
    });
    renderAdmin();
    await screen.findByRole("table", { name: "משתמשים" });
    await user.selectOptions(screen.getByLabelText("תפקיד של דנה"), "rep");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ role: "rep" }));
    await user.click(screen.getByRole("button", { name: "השבתת דנה" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(2));
    await user.click(screen.getByRole("button", { name: "השבתת מנהלת" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("של עצמך");
  });

  it("deletes a user only after a confirmation", async () => {
    const user = userEvent.setup();
    const calls = stubApi(listUsers, (url, init) =>
      init?.method === "DELETE" && url.endsWith("/u1") ? json(null, 204) : undefined,
    );
    renderAdmin();
    await screen.findByRole("table", { name: "משתמשים" });
    await user.click(screen.getByRole("button", { name: "מחיקת דנה" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("יחד עם כל השיחות");
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "מחיקה" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "מחיקת דנה" })).toBeNull());
    expect(calls.find((c) => c.method === "DELETE")?.url).toContain("/admin/users/u1");
  });
});

describe("pages by role", () => {
  function renderAt(path: string, user: AuthUser | null) {
    resetAuthForTests(user);
    return render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>,
    );
  }
  const me = (role: string): Route => (url) =>
    url.endsWith("/auth/me") ? json({ name: "דנה לוי", role }) : undefined;

  it("/admin is the admin's; anyone else sees the not-found page", async () => {
    stubApi(me("employee"));
    renderAt("/admin", USER("employee"));
    expect(await screen.findByText("הדף לא נמצא")).toBeInTheDocument();
  });

  it("/admin and /rep, logged out, go to the landing page", async () => {
    stubApi();
    renderAt("/admin", null);
    expect(await screen.findByRole("form", { name: "כניסה לעובדים" })).toBeInTheDocument();
  });

  it("/rep is the rep's only: an admin does not get the inbox", async () => {
    stubApi(me("admin"));
    renderAt("/rep", USER("admin"));
    expect(await screen.findByText("הדף לא נמצא")).toBeInTheDocument();
  });

  it("/c/:id of a conversation that is not yours is the not-found view", async () => {
    stubApi(me("employee"), (url) =>
      url.includes("/sessions/") && url.endsWith("/events") ? json({ detail: "x" }, 404) : undefined,
    );
    renderAt("/c/someone-elses", USER("employee"));
    expect(await screen.findByText("הדף לא נמצא")).toBeInTheDocument();
    expect(getAuth()).not.toBeNull(); // a 404 is not a logout
  });
});
