"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

const DEFAULT_MESSAGES = ["Setting up your workspace…", "Checking your connection…", "Almost there…"];

/** Full-screen loading state — shown while auth/scope resolves (AuthGuard) or a route decides
 * where to send the user (app/page.tsx). A plain "Loading…" string reads as broken on first
 * paint; this gives the wait a heartbeat (literally, for a health-resource app) instead. */
export function LoadingScreen({ message }: { message?: string }) {
  const [messageIndex, setMessageIndex] = useState(0);
  const messages = message ? [message] : DEFAULT_MESSAGES;

  useEffect(() => {
    if (messages.length <= 1) return;
    const interval = setInterval(() => setMessageIndex((i) => (i + 1) % messages.length), 2200);
    return () => clearInterval(interval);
  }, [messages.length]);

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center gap-6 animate-fade-in">
      <div className="relative w-20 h-20 flex items-center justify-center">
        <span className="absolute inset-0 rounded-full bg-brand-teal-wash animate-pulse-ring" />
        <span className="absolute inset-0 rounded-full bg-brand-teal-wash animate-pulse-ring [animation-delay:0.6s]" />
        <span className="relative w-14 h-14 rounded-full bg-brand-teal p-[2px] animate-breathe">
          <span className="w-full h-full rounded-full bg-white flex items-center justify-center overflow-hidden">
            <Image src="/logo.png" alt="HealthResQ" width={56} height={56} priority />
          </span>
        </span>
      </div>

      <div className="flex flex-col items-center gap-2">
        <p className="text-headline">HealthResQ</p>
        <div key={messageIndex} className="flex items-center gap-2 animate-fade-in">
          <p className="text-footnote text-label-secondary">{messages[messageIndex]}</p>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot" />
            <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot [animation-delay:0.15s]" />
            <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot [animation-delay:0.3s]" />
          </span>
        </div>
      </div>
    </div>
  );
}
