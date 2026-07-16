import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshSession, setAccessToken } from "../api/client";
import type { TokenResponse, User } from "../types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login(username: string, code: string): Promise<void>;
  logout(): Promise<void>;
  changeCode(currentCode: string, newCode: string): Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    refreshSession().then((result) => setUser(result.user)).catch(() => setAccessToken(null)).finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthState>(() => ({
    user,
    loading,
    async login(username, code) {
      const result = await api<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, code }),
      }, false);
      setAccessToken(result.access_token);
      setUser(result.user);
    },
    async logout() {
      try { await api("/api/v1/auth/logout", { method: "POST" }, false); } finally {
        setAccessToken(null);
        setUser(null);
      }
    },
    async changeCode(currentCode, newCode) {
      await api("/api/v1/auth/change-code", {
        method: "POST",
        body: JSON.stringify({ current_code: currentCode, new_code: newCode }),
      });
      setUser((current) => current ? { ...current, must_change_code: false } : null);
    },
  }), [loading, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider дотор ашиглана уу");
  return value;
}
