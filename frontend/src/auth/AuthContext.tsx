import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { AuthContext, type AuthValue } from "./context";
import { clearAuth, setAuth, useAuthState, type AuthUser } from "./authStore";

const SESSION_KEY = "compass.session";

/** The previous login's conversation id must not outlive it. */
function forgetConversation(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // nothing stored
  }
}

/**
 * Reads from GET /api/health whether accounts are on (never from a constant in the UI). Off, it
 * changes nothing. On, it keeps the login: it checks a stored token once with /auth/me.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const { user, notice } = useAuthState();

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((health) => alive && setEnabled(health.accounts === true))
      .catch(() => alive && setEnabled(false));
    return () => {
      alive = false;
    };
  }, []);

  // A token kept from earlier: still good? (a 401 here clears it, with the notice)
  const stored = user?.token ?? null;
  useEffect(() => {
    if (!enabled || !stored) return;
    api
      .me()
      .then((me) => {
        const current = user;
        const demo = me.demo ?? Boolean(current?.demo);
        if (
          current &&
          (current.name !== me.name || current.role !== me.role || Boolean(current.demo) !== demo)
        ) {
          const { token } = current;
          setAuth({ token, name: me.name, role: me.role, ...(demo ? { demo: true } : {}) });
        }
      })
      .catch(() => undefined);
    // only when the server's answer about accounts arrives, or the token changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, stored]);

  const grant = useCallback((granted: AuthUser) => {
    forgetConversation();
    setAuth(granted);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      status: enabled === null ? "loading" : !enabled ? "off" : user ? "in" : "out",
      user: enabled ? user : null,
      notice,
      login: async (email, password) => grant(await api.login(email.trim(), password)),
      register: async (body) => grant(await api.register({ ...body, email: body.email.trim() })),
      demoLogin: async (role) => grant({ ...(await api.demoLogin(role)), demo: true }),
      logout: async () => {
        try {
          await api.logout();
        } catch {
          // the token is forgotten here either way
        }
        forgetConversation();
        clearAuth();
      },
    }),
    [enabled, user, notice, grant],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
