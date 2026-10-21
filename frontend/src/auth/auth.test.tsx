import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { apiFetch } from "../api/client";
import { AuthProvider } from "./AuthContext";
import {
  EXPIRED_MESSAGE,
  getAuth,
  resetAuthForTests,
  setAuth,
  useAuthState,
} from "./authStore";
import { formatCodeInput, passwordProblem } from "./rules";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

const HEALTH_OFF = { ok: true, llm: "none", demo_scripts: null, dev_tools: false };
const HEALTH_ON = { ...HEALTH_OFF, accounts: true };
const LOGGED_IN = { token: "tok-1", name: "דנה", role: "employee" as const };

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function stubFetch(handler: Handler) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return handler(url, init);
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

describe("the login store", () => {
  it("keeps the login in sessionStorage only", () => {
    setAuth(LOGGED_IN);
    expect(JSON.parse(sessionStorage.getItem("compass.auth") ?? "null")).toEqual(LOGGED_IN);
    expect(localStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("a component sees a login as it is made", () => {
    function Probe() {
      const { user } = useAuthState();
      return <p>{user ? "in" : "out"}</p>;
    }
    render(<Probe />);
    expect(screen.getByText("out")).toBeInTheDocument();
    act(() => setAuth(LOGGED_IN));
    expect(screen.getByText("in")).toBeInTheDocument();
  });
});

describe("apiFetch", () => {
  it("adds the bearer when logged in, and leaves a call without a login alone", async () => {
    const calls = stubFetch(() => json({}));
    await apiFetch("/health");
    expect(calls[0]?.init).toEqual({}); // as it was: no header added
    setAuth(LOGGED_IN);
    await apiFetch("/conversations");
    expect(new Headers(calls[1]?.init?.headers).get("Authorization")).toBe("Bearer tok-1");
  });

  it("does not replace a bearer the caller set", async () => {
    setAuth(LOGGED_IN);
    const calls = stubFetch(() => json({}));
    await apiFetch("/tickets", { headers: { Authorization: "Bearer other" } });
    expect(new Headers(calls[0]?.init?.headers).get("Authorization")).toBe("Bearer other");
  });

  it("a 401 ends the login and says why", async () => {
    setAuth(LOGGED_IN);
    stubFetch(() => json({ detail: "x" }, 401));
    await apiFetch("/conversations");
    expect(getAuth()).toBeNull();
    expect(sessionStorage.getItem("compass.auth")).toBeNull();
    function Probe() {
      return <p>{useAuthState().notice}</p>;
    }
    render(<Probe />);
    expect(screen.getByText(EXPIRED_MESSAGE)).toBeInTheDocument();
  });

  it("a 401 without a login (a wrong password) changes nothing", async () => {
    stubFetch(() => json({ detail: "x" }, 401));
    const response = await apiFetch("/auth/login", { method: "POST" });
    expect(response.status).toBe(401);
    function Probe() {
      return <p>{useAuthState().notice ?? "no notice"}</p>;
    }
    render(<Probe />);
    expect(screen.getByText("no notice")).toBeInTheDocument();
  });
});

describe("the rules", () => {
  it("formats the invite code as it is typed or pasted", () => {
    expect(formatCodeInput("abcde")).toBe("ABCDE");
    expect(formatCodeInput("abcdef")).toBe("ABCDE-F");
    expect(formatCodeInput(" abcde-fghjk99 ")).toBe("ABCDE-FGHJK");
    expect(formatCodeInput("")).toBe("");
  });

  it("checks the password like the server", () => {
    expect(passwordProblem("short", "a@b.co")).toContain("10 עד 128");
    expect(passwordProblem("x".repeat(129), "a@b.co")).toContain("10 עד 128");
    expect(passwordProblem("Some.Address@Company.co.il", "some.address@company.co.il")).toContain(
      "שונה מהמייל",
    );
    expect(passwordProblem("a long new password", "a@b.co")).toBeNull();
  });
});

function renderApp(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("the flag comes from the API", () => {
  it("accounts off: no landing page, the app as it was", async () => {
    stubFetch((url) => (url.endsWith("/health") ? json(HEALTH_OFF) : new Response(null, { status: 404 })));
    renderApp("/");
    await waitFor(() => expect(screen.queryByRole("status", { name: "טוען" })).toBeNull());
    expect(screen.queryByText("כניסה לעובדים")).toBeNull();
    expect(screen.queryByRole("heading", { name: /כך תוכלו לדעת/ })).toBeNull();
    // and /register is not a page there
    renderApp("/register");
    expect(await screen.findByText("הדף לא נמצא")).toBeInTheDocument();
  });

  it("accounts on and logged out: the landing page", async () => {
    stubFetch(() => json(HEALTH_ON));
    renderApp("/");
    expect(
      await screen.findByRole("heading", { level: 1, name: /כך תוכלו לדעת בדיוק כמה נשאר בנטו,\s*לפני שבוחרים רכב\./ }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("יועץ הרכב של שטראוס").length).toBeGreaterThanOrEqual(2); // hero, footer
    expect(screen.getByRole("form", { name: "כניסה לעובדים" })).toBeInTheDocument();
    expect(screen.getByText("המודל לא מחשב כסף. אף פעם.")).toBeInTheDocument();
    expect(screen.getByText("השומר בודק")).toBeInTheDocument();
    expect(screen.getByText("פותח במסגרת האתגר של קבוצת שטראוס")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "הרשמה ראשונה" })).toHaveAttribute("href", "/register");
  });

  it("the demo card is one labelled picture with the two E-001 figures", async () => {
    stubFetch(() => json(HEALTH_ON));
    renderApp("/");
    const card = await screen.findByRole("img", { name: /דוגמה/ });
    expect(card).toHaveAccessibleName(/661.*ממתינה לנציג.*611.*סופי/);
  });

  it("a stored login the server refuses goes back to the landing page with the notice", async () => {
    setAuth(LOGGED_IN);
    stubFetch((url) =>
      url.endsWith("/health") ? json(HEALTH_ON) : json({ detail: "expired" }, 401),
    );
    renderApp("/");
    expect(await screen.findByText(EXPIRED_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "כניסה לעובדים" })).toBeInTheDocument();
  });
});

describe("login", () => {
  it("shows the server's message and clears the password", async () => {
    const user = userEvent.setup();
    stubFetch((url) =>
      url.endsWith("/health") ? json(HEALTH_ON) : json({ detail: "מייל או סיסמה שגויים" }, 401),
    );
    renderApp("/");
    await user.type(await screen.findByLabelText("מייל"), "dana@example.com");
    await user.type(screen.getByLabelText("סיסמה"), "wrong password");
    await user.click(screen.getByRole("button", { name: "כניסה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("מייל או סיסמה שגויים");
    expect(screen.getByLabelText("סיסמה")).toHaveValue("");
    expect(getAuth()).toBeNull();
  });

  it("a good login keeps the token in sessionStorage and leaves the landing page", async () => {
    const user = userEvent.setup();
    const calls = stubFetch((url) => {
      if (url.endsWith("/health")) return json(HEALTH_ON);
      if (url.endsWith("/auth/login")) return json(LOGGED_IN);
      return json({}, 404);
    });
    renderApp("/");
    await user.type(await screen.findByLabelText("מייל"), " dana@example.com ");
    await user.type(screen.getByLabelText("סיסמה"), "correct horse battery");
    await user.click(screen.getByRole("button", { name: "כניסה" }));
    await waitFor(() => expect(getAuth()?.token).toBe("tok-1"));
    const login = calls.find((c) => c.url.endsWith("/auth/login"));
    expect(JSON.parse(String(login?.init?.body))).toEqual({
      email: "dana@example.com",
      password: "correct horse battery",
    });
    expect(screen.queryByRole("form", { name: "כניסה לעובדים" })).toBeNull();
  });
});

describe("register", () => {
  async function fill(user: ReturnType<typeof userEvent.setup>, password: string, confirm = password) {
    await user.type(await screen.findByLabelText("מייל"), "new@example.com");
    await user.type(screen.getByLabelText("קוד הזמנה"), "abcdefghjk");
    await user.type(screen.getByLabelText("השם שלך"), "נועה");
    await user.type(screen.getByLabelText(/^סיסמה/), password);
    await user.type(screen.getByLabelText("אימות סיסמה"), confirm);
  }

  it("formats the code as typed", async () => {
    const user = userEvent.setup();
    stubFetch(() => json(HEALTH_ON));
    renderApp("/register");
    await user.type(await screen.findByLabelText("קוד הזמנה"), "abcdefghjk");
    expect(screen.getByLabelText("קוד הזמנה")).toHaveValue("ABCDE-FGHJK");
  });

  it("checks the password before it submits anything", async () => {
    const user = userEvent.setup();
    const calls = stubFetch(() => json(HEALTH_ON));
    renderApp("/register");
    await fill(user, "short");
    await user.click(screen.getByRole("button", { name: "הרשמה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("באורך 10 עד 128 תווים");
    expect(calls.some((c) => c.url.endsWith("/auth/register"))).toBe(false);
  });

  it("wants the two passwords to match", async () => {
    const user = userEvent.setup();
    stubFetch(() => json(HEALTH_ON));
    renderApp("/register");
    await fill(user, "a long new password", "a long new passwore");
    await user.click(screen.getByRole("button", { name: "הרשמה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("זהות");
  });

  it("shows the server's one generic message for an invite problem", async () => {
    const user = userEvent.setup();
    stubFetch((url) =>
      url.endsWith("/health") ? json(HEALTH_ON) : json({ detail: "הקוד או המייל אינם תקינים" }, 400),
    );
    renderApp("/register");
    await fill(user, "a long new password");
    await user.click(screen.getByRole("button", { name: "הרשמה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("הקוד או המייל אינם תקינים");
  });

  it("registers, logs in and leaves the page", async () => {
    const user = userEvent.setup();
    const calls = stubFetch((url) =>
      url.endsWith("/health")
        ? json(HEALTH_ON)
        : url.endsWith("/auth/register")
          ? json({ token: "tok-9", name: "נועה", role: "employee" }, 201)
          : json({}, 404),
    );
    renderApp("/register");
    await fill(user, "a long new password");
    await user.click(screen.getByRole("button", { name: "הרשמה" }));
    await waitFor(() => expect(getAuth()?.name).toBe("נועה"));
    const sent = JSON.parse(String(calls.find((c) => c.url.endsWith("/auth/register"))?.init?.body));
    expect(sent).toEqual({
      email: "new@example.com",
      code: "ABCDE-FGHJK",
      name: "נועה",
      password: "a long new password",
    });
  });
});
