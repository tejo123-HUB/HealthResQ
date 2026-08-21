"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { clearToken, setToken } from "@/lib/api/client";
import { ops } from "@/lib/api/ops";
import type { Facility, Scope } from "@/lib/api/types";
import { ensureUnitKeyPair } from "@/lib/communication/mailboxService";

const SCOPE_STORAGE_KEY = "healthresq.scope";

type AuthState = {
  scope: Scope | null;
  facility: Facility | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<{ scope: Scope; facility: Facility | null }>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

function readStoredScope(): Scope | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SCOPE_STORAGE_KEY);
  return raw ? (JSON.parse(raw) as Scope) : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [scope, setScope] = useState<Scope | null>(null);
  const [facility, setFacility] = useState<Facility | null>(null);
  const [loading, setLoading] = useState(true);

  // Returns the loaded facility (or null) directly, not just via the state setter — a caller that
  // needs to navigate immediately after (e.g. login) can't rely on a state update having landed
  // by the time its own await resolves.
  const loadFacility = useCallback(async (s: Scope): Promise<Facility | null> => {
    if (s.level !== "FACILITY") {
      setFacility(null);
      return null;
    }
    const f = await ops.getFacility(s.id);
    setFacility(f);
    // COMM-02: provision (or re-provision, on key loss) this facility's keypair as soon as we
    // know its identity, so the inbox has something to decrypt by the time it's rendered.
    await ensureUnitKeyPair(s.id);
    return f;
  }, []);

  useEffect(() => {
    const stored = readStoredScope();
    if (stored) {
      setScope(stored);
      loadFacility(stored).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [loadFacility]);

  const login = useCallback(
    async (username: string, password: string) => {
      const { token, scope: newScope } = await ops.login(username, password);
      setToken(token);
      window.localStorage.setItem(SCOPE_STORAGE_KEY, JSON.stringify(newScope));
      setScope(newScope);
      const newFacility = await loadFacility(newScope);
      return { scope: newScope, facility: newFacility };
    },
    [loadFacility]
  );

  const logout = useCallback(() => {
    clearToken();
    window.localStorage.removeItem(SCOPE_STORAGE_KEY);
    setScope(null);
    setFacility(null);
  }, []);

  return <AuthContext.Provider value={{ scope, facility, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
