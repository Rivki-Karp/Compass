import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function renderAt(path: string, dev: boolean) {
  vi.stubEnv("DEV", dev);
  vi.resetModules(); // App reads import.meta.env.DEV when it loads
  const { AppRoutes } = await import("../App");
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("unknown UI routes", () => {
  it("show a Hebrew not-found page with a link home, not a blank screen", async () => {
    await renderAt("/no-such-page", false);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("הדף לא נמצא");
    expect(screen.getByRole("link", { name: "לדף הבית" })).toHaveAttribute("href", "/");
  });

  it("the style guide is dev-only: in the production build it is not found", async () => {
    await renderAt("/__styleguide", false);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("הדף לא נמצא");
  });

  it("in development the style guide route exists", async () => {
    await renderAt("/__styleguide", true);
    expect(screen.queryByText("הדף לא נמצא")).toBeNull();
  });
});
