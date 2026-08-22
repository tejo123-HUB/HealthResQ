"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { BrandBackdrop } from "@/components/BrandBackdrop";
import { Button } from "@/components/hig/Button";
import { Card } from "@/components/hig/Card";
import { Disclosure } from "@/components/hig/Disclosure";
import { Icon } from "@/components/hig/Icon";
import { LanguageSheet } from "@/components/LanguageSheet";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthContext";
import { homePathForScope } from "@/lib/auth/routing";
import { useReducedMotion } from "@/lib/hooks/useReducedMotion";
import { useLocale } from "@/lib/i18n/LocaleProvider";

export default function LoginPage() {
  const { t } = useTranslation(["login", "common"]);
  const { login, updateLocale } = useAuth();
  const { locale } = useLocale();
  const router = useRouter();
  const reducedMotion = useReducedMotion();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [languageOpen, setLanguageOpen] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { scope, facility } = await login(username, password);
      // Navigate straight to the destination — routing through "/" and letting its own redirect
      // effect fire a second router.replace() right behind this one drops the second navigation
      // in Next.js App Router (a real race, not a timing fluke).
      router.replace(homePathForScope(scope.level, facility?.type));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("login:loginFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <BrandBackdrop>
      <div className="min-h-[85vh] flex flex-col items-center justify-center px-4 relative">
        <button
          onClick={() => setLanguageOpen(true)}
          aria-label={t("common:language")}
          className="absolute top-4 right-4 sm:top-6 sm:right-6 w-9 h-9 flex items-center justify-center rounded-hig text-label-secondary hover:bg-fill-thin active:bg-fill-regular active:scale-90 transition-hig"
        >
          <Icon name="globe" className="w-4.5 h-4.5" />
        </button>
        <div className="max-w-sm w-full flex flex-col items-center">
          <div className={`mb-5 ${reducedMotion ? "" : "animate-scale-in"}`}>
            <div className={reducedMotion ? "" : "animate-breathe"}>
              <Image src="/logo.png" alt="HealthResQ" width={92} height={92} priority className="rounded-3xl" />
            </div>
          </div>

          <div
            className={`text-center ${reducedMotion ? "" : "animate-fade-in-up"}`}
            style={reducedMotion ? undefined : { animationDelay: "80ms" }}
          >
            <h1 className="text-title1">HealthResQ</h1>
            <p className="text-body text-label-secondary mt-1 mb-6">{t("login:tagline")}</p>
          </div>

          <div
            className={`w-full ${reducedMotion ? "" : "animate-fade-in-up"}`}
            style={reducedMotion ? undefined : { animationDelay: "150ms" }}
          >
            <Card>
              <form onSubmit={onSubmit} className="flex flex-col gap-4">
                <label className="flex flex-col gap-1">
                  <span className="text-footnote text-label-secondary">{t("login:username")}</span>
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
                    autoComplete="username"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-footnote text-label-secondary">{t("login:password")}</span>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full text-body bg-bg-secondary rounded-hig pl-3 pr-10 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((s) => !s)}
                      aria-label={showPassword ? t("login:hidePassword") : t("login:showPassword")}
                      aria-pressed={showPassword}
                      className="absolute right-1 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-hig text-label-secondary hover:bg-fill-thin active:scale-90 transition-hig"
                    >
                      <Icon name={showPassword ? "eyeOff" : "eye"} className="w-4.5 h-4.5" />
                    </button>
                  </div>
                </label>
                {error && (
                  <p className={`text-footnote text-tint-red ${reducedMotion ? "" : "animate-fade-in-up"}`}>{error}</p>
                )}
                <Button type="submit" disabled={submitting} className="flex items-center justify-center gap-2">
                  {submitting ? (
                    <>
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot" />
                        <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot [animation-delay:0.15s]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot [animation-delay:0.3s]" />
                      </span>
                      {t("common:signingIn")}
                    </>
                  ) : (
                    t("common:signIn")
                  )}
                </Button>
              </form>
            </Card>
          </div>

          <Disclosure
            summary={t("login:demoAccounts")}
            className={`mt-4 ${reducedMotion ? "" : "animate-fade-in-up"}`}
          >
            <p className="text-caption1 text-label-tertiary">{t("login:demoAccountsList")}</p>
          </Disclosure>
        </div>
      </div>
      <LanguageSheet
        open={languageOpen}
        current={locale}
        onSelect={(code) => {
          updateLocale(code);
          setLanguageOpen(false);
        }}
        onDismiss={() => setLanguageOpen(false)}
      />
    </BrandBackdrop>
  );
}
