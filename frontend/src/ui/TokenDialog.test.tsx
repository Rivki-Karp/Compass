import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TOKEN_NOT_CONFIGURED, tokenCheck } from "../lib/tokenCheck";
import { RepPage } from "../routes/RepPage";
import { TokenDialog } from "./TokenDialog";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function dialog(props: Partial<Parameters<typeof TokenDialog>[0]> = {}) {
  render(
    <TokenDialog
      open
      title="מצב שופטים"
      description="…"
      label="טוקן מנהל"
      verify={vi.fn().mockResolvedValue("ok")}
      onCancel={vi.fn()}
      onAccept={vi.fn()}
      {...props}
    />,
  );
}

describe("an empty token on the server", () => {
  it("503 means the token is not set; 401 is a wrong token", () => {
    expect(tokenCheck(200)).toBe("ok");
    expect(tokenCheck(401)).toBe("wrong");
    expect(tokenCheck(503)).toBe("not_configured");
    expect(tokenCheck(500)).toBe("unavailable");
  });

  it("the dialog says so up front and does not ask for a token", () => {
    dialog({ notConfigured: true });
    expect(screen.getByRole("alert")).toHaveTextContent(TOKEN_NOT_CONFIGURED);
    expect(screen.getByLabelText("טוקן מנהל")).toBeDisabled();
    expect(screen.getByRole("button", { name: "אישור" })).toBeDisabled();
  });

  it("a 503 while verifying shows the same message", async () => {
    dialog({ verify: vi.fn().mockResolvedValue("not_configured") });
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("טוקן מנהל"), "anything");
    await user.click(screen.getByRole("button", { name: "אישור" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "טוקן לא הוגדר בשרת. ראו docs/demo-runbook.md",
    );
  });

  it("/rep says the token is not set when the server has none", async () => {
    const health = { ok: true, llm: "anthropic", demo_scripts: null, dev_tools: false };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ...health, auth: { rep: false, admin: true } }), {
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    render(
      <MemoryRouter initialEntries={["/rep"]}>
        <RepPage />
      </MemoryRouter>,
    );
    const alerts = await screen.findAllByText(TOKEN_NOT_CONFIGURED);
    expect(alerts.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText("טוקן נציג")).toBeDisabled();
  });
});
