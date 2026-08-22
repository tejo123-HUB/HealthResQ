import type { Metadata } from "next";
import Script from "next/script";
import type { ReactNode } from "react";
import { Nav } from "@/components/Nav";
import { PageTransition } from "@/components/PageTransition";
import { AuthProvider } from "@/lib/auth/AuthContext";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";
import { ToastProvider } from "@/lib/toast/ToastProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthResQ",
  description: "Federated agentic health-resource and supply-chain resilience platform",
};

// Server-rendered HTML already carries the light default below, so this only ever needs to flip
// the attribute for a returning user who chose dark — never for the (common) light case. Runs
// before hydration so that flip never flashes light-then-dark either.
const THEME_INIT_SCRIPT = `
  try {
    if (localStorage.getItem('healthresq.theme') === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  } catch (e) {}
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <Script id="theme-init" strategy="beforeInteractive">
          {THEME_INIT_SCRIPT}
        </Script>
      </head>
      <body className="bg-bg-secondary min-h-screen">
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <Nav />
              <main className="max-w-5xl mx-auto px-4 py-6">
                <PageTransition>{children}</PageTransition>
              </main>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
