import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdminPage } from "../admin/AdminPage";
import { ApiError, type AdminUser } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import { getAuth, resetAuthForTests } from "../auth/authStore";
import { DemoBanner } from "../home/DemoBanner";
import { DemoQuickAccess } from "../landing/DemoQuickAccess";
import { JudgesUnlockDialog } from "./JudgesUnlockDialog";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const HEALTH = { ok: true, llm: "none", demo_scripts: null, dev_tools: false, accounts: true };

beforeEach(() => resetAuthForTests(null));
afterEach(() => {
  vi.unstubAllGlobals();
  resetAuthForTests(null);
  sessionStorage.clear();
});

function dialog(unlock = vi.fn().mockResolvedValue(undefined)) {
  const onCancel = vi.fn();
  const onUnlocked = vi.fn();
  render(<JudgesUnlockDialog open unlock={unlock} onCancel={onCancel} onUnlocked={onUnlocked} />);
  return { unlock, onCancel, onUnlocked };
}

describe("the judges unlock dialog", () => {
  it("opens with its title, its text, a password field and the two buttons", () => {
    dialog();
    const box = screen.getByRole("dialog", { name: "מצב שופטים" });
    expect(box).toHaveTextContent("הזינו את סיסמת המנהל כדי לראות את חדר המנועים");
    expect(within(box).getByLabelText("סיסמת מנהל")).toHaveAttribute("type", "password");
    expect(within(box).getByRole("button", { name: "פתיחה" })).toBeEnabled();
    expect(within(box).getByRole("button", { name: "ביטול" })).toBeEnabled();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("a right password: it is sent, the dialog reports success and keeps nothing", async () => {
    const user = userEvent.setup();
    const { unlock, onUnlocked } = dialog();
    await user.type(screen.getByLabelText("סיסמת מנהל"), "the admin password");
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    await waitFor(() => expect(onUnlocked).toHaveBeenCalledTimes(1));
    expect(unlock).toHaveBeenCalledWith("the admin password");
    expect(screen.getByLabelText("סיסמת מנהל")).toHaveValue("");
  });

  it("a wrong password: the one generic error, the field is cleared, the dialog stays", async () => {
    const user = userEvent.setup();
    const { onUnlocked } = dialog(vi.fn().mockRejectedValue(new ApiError(401, "הסיסמה שגויה")));
    await user.type(screen.getByLabelText("סיסמת מנהל"), "nope");
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("הסיסמה שגויה");
    expect(screen.getByLabelText("סיסמת מנהל")).toHaveValue("");
    expect(screen.getByLabelText("סיסמת מנהל")).toHaveAttribute("aria-invalid", "true");
    expect(onUnlocked).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("an empty password is the same error, without asking the server", async () => {
    const user = userEvent.setup();
    const { unlock } = dialog();
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    expect(screen.getByRole("alert")).toHaveTextContent("הסיסמה שגויה");
    expect(unlock).not.toHaveBeenCalled();
  });

  it("locked out: the server's words, with their hint; any other failure: try again", async () => {
    const user = userEvent.setup();
    dialog(
      vi
        .fn()
        .mockRejectedValueOnce(new ApiError(429, "הסיסמה שגויה. נסו שוב בעוד כמה דקות"))
        .mockRejectedValueOnce(new Error("network")),
    );
    await user.type(screen.getByLabelText("סיסמת מנהל"), "x");
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("נסו שוב בעוד כמה דקות");
    await user.type(screen.getByLabelText("סיסמת מנהל"), "x");
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("לא ניתן לאמת כרגע. נסו שוב."),
    );
  });

  it("while it checks, the button says so and cannot be pressed twice", async () => {
    const user = userEvent.setup();
    let release: () => void = () => undefined;
    const { unlock } = dialog(vi.fn(() => new Promise<void>((resolve) => (release = resolve))));
    await user.type(screen.getByLabelText("סיסמת מנהל"), "x");
    await user.click(screen.getByRole("button", { name: "פתיחה" }));
    expect(await screen.findByRole("button", { name: "בודק…" })).toBeDisabled();
    release();
    await waitFor(() => expect(screen.getByRole("button", { name: "פתיחה" })).toBeEnabled());
    expect(unlock).toHaveBeenCalledTimes(1);
  });

  it("ביטול and Esc both cancel, and what was typed is gone", async () => {
    const user = userEvent.setup();
    const { onCancel } = dialog();
    await user.type(screen.getByLabelText("סיסמת מנהל"), "secret");
    await user.click(screen.getByRole("button", { name: "ביטול" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("סיסמת מנהל")).toHaveValue("");
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it("traps focus: Tab cycles inside the dialog and never leaves it", async () => {
    const user = userEvent.setup();
    render(
      <>
        <button>behind</button>
        <JudgesUnlockDialog open unlock={vi.fn()} onCancel={vi.fn()} onUnlocked={vi.fn()} />
      </>,
    );
    const box = screen.getByRole("dialog");
    expect(box).toContainElement(document.activeElement as HTMLElement);
    for (let i = 0; i < 6; i += 1) {
      await user.tab();
      expect(box).toContainElement(document.activeElement as HTMLElement);
    }
  });
});

describe("the demo quick access", () => {
  function stub(health: object, onDemo?: (body: unknown) => Response) {
    const calls: { url: string; body?: unknown }[] = [];
    let granted: { name: string; role: string } = { name: "x", role: "employee" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
        if (url.endsWith("/health")) return json(health);
        if (url.endsWith("/auth/demo-login") && onDemo) {
          const reply = onDemo(calls.at(-1)?.body);
          if (reply.ok) granted = await reply.clone().json();
          return reply;
        }
        if (url.endsWith("/auth/me")) return json({ ...granted, demo: true });
        return json({}, 404);
      }),
    );
    return calls;
  }
  const renderQuick = () =>
    render(
      <MemoryRouter>
        <AuthProvider>
          <DemoQuickAccess />
        </AuthProvider>
      </MemoryRouter>,
    );

  it("is not there when the server does not report the flag", async () => {
    const calls = stub(HEALTH);
    renderQuick();
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/health"))).toBe(true));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByText("כניסה מהירה להתנסות")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows three buttons with their hints and the shared-account line", async () => {
    stub({ ...HEALTH, demo_login: true });
    renderQuick();
    const section = await screen.findByRole("region", { name: "כניסה מהירה להתנסות" });
    const buttons = within(section).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual([
      "עובדתצ'אט, תלוש והיסטוריה",
      "נציגמענה לפניות",
      "מנהלתהזמנת משתמשים · מצב שופטים",
    ]);
    expect(section).toHaveTextContent("חשבונות הדגמה משותפים. אל תזינו מידע אישי אמיתי.");
  });

  it("a click logs in as that role with no password, and marks the login as a demo", async () => {
    const user = userEvent.setup();
    const calls = stub({ ...HEALTH, demo_login: true }, () =>
      json({ token: "t-demo", name: "Demo rep", role: "rep" }),
    );
    renderQuick();
    await user.click(await screen.findByRole("button", { name: /נציג/ }));
    await waitFor(() => expect(getAuth()).toMatchObject({ token: "t-demo", role: "rep", demo: true }));
    const sent = calls.find((c) => c.url.endsWith("/auth/demo-login"));
    expect(sent?.body).toEqual({ role: "rep" });
  });

  it("a failure says so and leaves nobody logged in", async () => {
    const user = userEvent.setup();
    stub({ ...HEALTH, demo_login: true }, () => json({ detail: "Not Found" }, 404));
    renderQuick();
    await user.click(await screen.findByRole("button", { name: /עובדת/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("לא ניתן להיכנס כרגע");
    expect(getAuth()).toBeNull();
  });
});

describe("the demo banner", () => {
  function renderBanner() {
    return render(
      <MemoryRouter>
        <AuthProvider>
          <DemoBanner />
        </AuthProvider>
      </MemoryRouter>,
    );
  }
  function stubMe(demo: boolean) {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        if (url.endsWith("/health")) return json(HEALTH);
        if (url.endsWith("/auth/me")) return json({ name: "Demo", role: "employee", demo });
        if (url.endsWith("/auth/logout")) return new Response(null, { status: 204 });
        return json({}, 404);
      }),
    );
    return calls;
  }

  it("is there for a demo login, with a way to log out", async () => {
    const user = userEvent.setup();
    const calls = stubMe(true);
    resetAuthForTests({ token: "t", name: "Demo", role: "employee", demo: true });
    renderBanner();
    const banner = await screen.findByRole("region", { name: "חשבון הדגמה" });
    expect(banner).toHaveTextContent("את/ה בחשבון הדגמה משותף");
    await user.click(within(banner).getByRole("button", { name: "התנתקות" }));
    await waitFor(() => expect(getAuth()).toBeNull());
    expect(calls.some((url) => url.endsWith("/auth/logout"))).toBe(true);
  });

  it("is not there for an ordinary login", async () => {
    stubMe(false);
    resetAuthForTests({ token: "t", name: "Dana", role: "employee" });
    renderBanner();
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
    expect(screen.queryByRole("region", { name: "חשבון הדגמה" })).toBeNull();
  });
});

describe("the admin page in a demo", () => {
  const stamp = "2026-10-01T08:00:00+00:00";
  const USERS: AdminUser[] = [
    { id: "d1", email: "demo-employee@example.com", name: "עובדת הדגמה", role: "employee", status: "active", created_at: stamp, last_login_at: null, demo: true },
    { id: "v1", email: "visitor@example.com", name: "מבקר", role: "employee", status: "active", created_at: stamp, last_login_at: null, demo: false },
  ];
  function renderAdmin(demo: boolean) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/admin/users")) return json(USERS);
        if (url.endsWith("/health")) return json(HEALTH);
        if (url.endsWith("/auth/me")) return json({ name: "Demo admin", role: "admin", demo });
        return json({}, 404);
      }),
    );
    resetAuthForTests({ token: "t", name: "Demo admin", role: "admin", ...(demo ? { demo: true } : {}) });
    return render(
      <MemoryRouter initialEntries={["/admin"]}>
        <AuthProvider>
          <AdminPage />
        </AuthProvider>
      </MemoryRouter>,
    );
  }

  it("a demo account's role, status and delete are disabled, each with the reason", async () => {
    renderAdmin(true);
    const table = await screen.findByRole("table", { name: "משתמשים" });
    const rows = within(table).getAllByRole("row");
    const demoRow = rows.find((r) => r.textContent?.includes("demo-employee@example.com"));
    if (!demoRow) throw new Error("no demo row");
    const reason = "אי אפשר למחוק אותו";
    for (const control of [
      within(demoRow).getByRole("combobox"),
      within(demoRow).getByRole("button", { name: /השבתת/ }),
      within(demoRow).getByRole("button", { name: /מחיקת/ }),
    ]) {
      expect(control).toBeDisabled();
      expect(control.getAttribute("title")).toContain(reason);
    }
    // a user invited from the demo is theirs to manage
    const visitorRow = rows.find((r) => r.textContent?.includes("visitor@example.com"));
    if (!visitorRow) throw new Error("no visitor row");
    expect(within(visitorRow).getByRole("button", { name: /מחיקת/ })).toBeEnabled();
  });

  it("a demo session cannot pick admin for an invite", async () => {
    renderAdmin(true);
    await screen.findByRole("table", { name: "משתמשים" });
    const options = within(screen.getByLabelText("תפקיד", { selector: "#invite-role" })).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["עובד/ת", "נציג/ה"]);
  });

  it("an ordinary admin still can", async () => {
    renderAdmin(false);
    await screen.findByRole("table", { name: "משתמשים" });
    const options = within(screen.getByLabelText("תפקיד", { selector: "#invite-role" })).getAllByRole("option");
    expect(options).toHaveLength(3);
  });
});

describe("a wrong admin password is not the end of the login", () => {
  it("a 401 from the unlock keeps the login", async () => {
    const { api } = await import("../api/client");
    resetAuthForTests({ token: "t-1", name: "Dana", role: "employee" });
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "הסיסמה שגויה" }, 401)));
    await expect(api.judgesUnlock("nope")).rejects.toMatchObject({ status: 401 });
    expect(getAuth()).toMatchObject({ token: "t-1" });
    const sent = vi.mocked(fetch).mock.calls[0]?.[1]?.headers;
    expect(new Headers(sent).get("Authorization")).toBe("Bearer t-1");
  });
});
