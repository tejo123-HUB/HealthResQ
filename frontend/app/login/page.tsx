"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { BrandBackdrop } from "@/components/BrandBackdrop";
import { Button } from "@/components/hig/Button";
import { Card } from "@/components/hig/Card";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthContext";
import { homePathForScope } from "@/lib/auth/routing";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("operator.phc-001");
  const [password, setPassword] = useState("demo-pass-123");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <BrandBackdrop>
      <div className="min-h-[85vh] flex flex-col items-center justify-center px-4">
        <div className="max-w-sm w-full flex flex-col items-center">
          <div className="animate-scale-in mb-5">
            <div className="animate-breathe">
              <Image src="/logo.png" alt="HealthResQ" width={92} height={92} priority className="rounded-3xl" />
            </div>
          </div>

          <div className="text-center animate-fade-in-up" style={{ animationDelay: "80ms" }}>
            <h1 className="text-title1">HealthResQ</h1>
            <p className="text-body text-label-secondary mt-1 mb-6">
              Sign in with your facility or authority account.
            </p>
          </div>

          <div className="w-full animate-fade-in-up" style={{ animationDelay: "150ms" }}>
            <Card className="shadow-sm">
              <form onSubmit={onSubmit} className="flex flex-col gap-4">
                <label className="flex flex-col gap-1">
                  <span className="text-footnote text-label-secondary">Username</span>
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
                    autoComplete="username"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-footnote text-label-secondary">Password</span>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
                    autoComplete="current-password"
                  />
                </label>
                {error && (
                  <p className="text-footnote text-tint-red animate-fade-in-up">{error}</p>
                )}
                <Button type="submit" disabled={submitting} className="flex items-center justify-center gap-2">
                  {submitting ? (
                    <>
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot" />
                        <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot [animation-delay:0.15s]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot [animation-delay:0.3s]" />
                      </span>
                      Signing in…
                    </>
                  ) : (
                    "Sign in"
                  )}
                </Button>
              </form>
            </Card>
          </div>

          <p
            className="text-caption1 text-label-tertiary mt-4 text-center animate-fade-in-up"
            style={{ animationDelay: "220ms" }}
          >
            Demo accounts: operator.phc-001, district.krishna, state.andhra-pradesh, national.india
            (password demo-pass-123).
          </p>
        </div>
      </div>
    </BrandBackdrop>
  );
}
