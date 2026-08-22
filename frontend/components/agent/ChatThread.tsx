"use client";

import { useEffect, useRef, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { TypewriterText } from "@/components/agent/TypewriterText";
import { Icon } from "@/components/hig/Icon";
import { useReducedMotion } from "@/lib/hooks/useReducedMotion";

// `typed` starts false only for a freshly-arrived agent reply — it flips to true once
// TypewriterText finishes revealing it, so scrolling back through history never re-types
// something already read. Same shape `AgentPane.tsx` keeps internally; factored out here so
// Compose's split-pane thread (`frontend/app/orders/new/page.tsx`) can reuse the identical
// message-list/bubble/typing-indicator markup without either screen importing the other's
// component (AgentPane owns its own "AI suggestion" card, which Compose has no use for).
export type ChatMessage = { role: "user" | "agent"; text: string; typed?: boolean };

/** The reusable half of `AgentPane.tsx`: a scrollable message list with typed-bubble reveal, a
 * typing indicator while a reply is in flight, and a send form. Callers own the `messages` array
 * (and the `typed` flag on each one) so they can react to what the agent said — e.g. Compose
 * parsing "change quantity to 40" out of a just-sent user turn to update a candidate card. */
export function ChatThread({
  messages,
  onSend,
  onMessageTyped,
  sending,
  placeholder,
  emptyHint,
  className = "",
  inputValue,
  onInputChange,
}: {
  messages: ChatMessage[];
  onSend: (text: string) => void | Promise<void>;
  onMessageTyped: (index: number) => void;
  sending: boolean;
  placeholder?: string;
  emptyHint?: string;
  className?: string;
  inputValue: string;
  onInputChange: (value: string) => void;
}) {
  const { t } = useTranslation(["agent", "common"]);
  const resolvedPlaceholder = placeholder ?? t("agent:askPlaceholder");
  const resolvedEmptyHint = emptyHint ?? t("agent:askHint");
  const scrollRef = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: reducedMotion ? "auto" : "smooth" });
  }, [messages.length, sending, reducedMotion]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = inputValue.trim();
    if (!text || sending) return;
    onInputChange("");
    void onSend(text);
  }

  return (
    <div className={`bg-bg rounded-hig border border-separator shadow-card flex flex-col ${className}`}>
      <div className="px-4 py-3 border-b border-separator text-footnote text-label-secondary uppercase flex items-center gap-1.5">
        <Icon name="pulse" className="w-3.5 h-3.5 text-tint-pink" />
        {t("agent:composeWithAssistant")}
      </div>
      <div ref={scrollRef} className="flex-1 flex flex-col gap-2 p-4 overflow-y-auto scroll-smooth">
        {messages.length === 0 && <p className="text-footnote text-label-tertiary">{resolvedEmptyHint}</p>}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-body rounded-hig px-3 py-2 max-w-[85%] shadow-card ${
              m.role === "user"
                ? "bg-tint-blue text-white self-end animate-slide-in-right"
                : "bg-bg-secondary text-label self-start animate-slide-in-left"
            }`}
          >
            {m.role === "agent" && !m.typed ? (
              <TypewriterText text={m.text} onDone={() => onMessageTyped(i)} speedMs={reducedMotion ? 0 : 12} />
            ) : (
              m.text
            )}
          </div>
        ))}
        {sending && (
          <div className="flex items-center gap-1 self-start bg-bg-secondary rounded-hig px-3 py-2.5 animate-fade-in">
            <span className={`w-1.5 h-1.5 rounded-full bg-label-tertiary ${reducedMotion ? "" : "animate-bounce-dot"}`} />
            <span
              className={`w-1.5 h-1.5 rounded-full bg-label-tertiary ${reducedMotion ? "" : "animate-bounce-dot [animation-delay:0.15s]"}`}
            />
            <span
              className={`w-1.5 h-1.5 rounded-full bg-label-tertiary ${reducedMotion ? "" : "animate-bounce-dot [animation-delay:0.3s]"}`}
            />
          </div>
        )}
      </div>
      <form onSubmit={handleSubmit} className="p-3 border-t border-separator flex items-center gap-2">
        <input
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder={resolvedPlaceholder}
          className="flex-1 text-body bg-bg-secondary rounded-hig px-3 min-h-[2.25rem] border border-separator outline-none transition-hig focus:border-tint-pink focus:ring-2 focus:ring-tint-pink-wash"
        />
        <button
          type="submit"
          disabled={sending || !inputValue.trim()}
          aria-label={t("common:send")}
          className="w-9 h-9 shrink-0 flex items-center justify-center rounded-hig bg-tint-pink text-white disabled:opacity-40 enabled:hover:shadow-card-hover active:opacity-70 active:scale-90 transition-hig"
        >
          <Icon name="chevronRight" className="w-4.5 h-4.5" />
        </button>
      </form>
    </div>
  );
}
