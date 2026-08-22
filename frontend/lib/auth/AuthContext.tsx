"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { clearToken, setToken } from "@/lib/api/client";
import { ops } from "@/lib/api/ops";
import type { Facility, Scope } from "@/lib/api/types";
import { ensureUnitKeyPair } from "@/lib/communication/mailboxService";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import { useToast } from "@/lib/toast/ToastProvider";

const SCOPE_STORAGE_KEY = "healthresq.scope";

type AuthState = {
  scope: Scope | null;
  facility: Facility | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<{ scope: Scope; facility: Facility | null }>;
  logout: () => void;
  /** Switches the active language immediately (via LocaleProvider) and, only when signed in,
   * persists it to the account in the background — the single callback both the pre-login and
   * post-login LanguageSheet instances call, so neither has to know which case it's in. */
  updateLocale: (code: string) => void;
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
  const { setLocale } = useLocale();
  const toast = useToast();

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
      // Cross-device locale sync: a restored session re-fetches the account's authoritative
      // preferredLocale (not just whatever this browser's own localStorage last cached) alongside
      // the existing facility load — parallel, not serial, so this doesn't add latency beyond what
      // the facility fetch already costs. Best-effort: an expired/failing token here just leaves
      // the locally-cached locale in place rather than blocking session restore on it.
      Promise.all([
        loadFacility(stored),
        ops
          .getMe()
          .then((me) => setLocale(me.preferredLocale))
          .catch(() => {}),
      ]).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadFacility]);

  const login = useCallback(
    async (username: string, password: string) => {
      const { token, scope: newScope, preferredLocale } = await ops.login(username, password);
      setToken(token);
      window.localStorage.setItem(SCOPE_STORAGE_KEY, JSON.stringify(newScope));
      setScope(newScope);
      setLocale(preferredLocale);
      const newFacility = await loadFacility(newScope);
      return { scope: newScope, facility: newFacility };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loadFacility]
  );

  const logout = useCallback(() => {
    clearToken();
    window.localStorage.removeItem(SCOPE_STORAGE_KEY);
    setScope(null);
    setFacility(null);
  }, []);

  const updateLocale = useCallback(
    (code: string) => {
      setLocale(code);
      if (!scope) return; // pre-login: local-only, gets bound automatically on next login
      ops.updateMyLocale(code).catch(() => {
        toast.error("Couldn't save your language choice to your account — it'll still apply on this device.");
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scope]
  );

  return (
    <AuthContext.Provider value={{ scope, facility, loading, login, logout, updateLocale }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
