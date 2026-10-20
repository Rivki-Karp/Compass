import { createContext, useContext } from "react";
import type { AuthUser } from "./authStore";

/**
 * "loading": the server has not said yet whether accounts are on. "off": COMPASS_AUTH=0, nothing
 * of this exists and the app is as it was. "out": accounts on, nobody logged in. "in": logged in.
 */
export type AuthStatus = "loading" | "off" | "out" | "in";

export interface AuthValue {
  status: AuthStatus;
  user: AuthUser | null;
  /** Why the login ended (a 401), shown once on the landing page. */
  notice: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (body: { email: string; code: string; name: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
}

const OFF: AuthValue = {
  status: "off",
  user: null,
  notice: null,
  login: () => Promise.reject(new Error("accounts are off")),
  register: () => Promise.reject(new Error("accounts are off")),
  logout: () => Promise.resolve(),
};

// Without a provider (the page tests render routes alone) accounts are off.
export const AuthContext = createContext<AuthValue>(OFF);

export const useAuth = (): AuthValue => useContext(AuthContext);
