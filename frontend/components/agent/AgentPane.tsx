"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import useSWR from "swr";
import { TypewriterText } from "@/components/agent/TypewriterText";
import { Icon } from "@/components/hig/Icon";
import { agent } from "@/lib/api/agent";
import { command } from "@/lib/api/command";
import type { Scope } from "@/lib/api/types";

// `typed` starts false only for a freshly-arrived agent reply — it flips to true once
// TypewriterText finishes revealing it, so scrolling back through history never re-types
// something you already read.
type ChatMessage = { role: "user" | "agent"; text: string; typed?: boolean };

/** Data lives in the main column; this pane is where the authority discusses it — the top AI
 * suggestion (the most recent pending recommendation in the caller's own scope, per CMD-09) plus
 * a chat thread for "what about instead…" questions (AGT-01). One persistent surface, not a
 * modal, so a question is always one tap away without leaving the workspace. */
export function AgentPane({ scope }: { scope: Scope }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { data: pending } = useSWR(["pending-recommendations", scope.level, scope.id], () =>
    command.listRecommendations("PENDING_REVIEW,OUTDATED")
  );
  const topRecommendation = pending?.[0];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, sending]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || sending) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: question, typed: true }]);
    setSending(true);
    try {
      const reply = await agent.ask(scope, question, topRecommendation ? { recommendationId: topRecommendation.id } : undefined);
      setMessages((m) => [...m, { role: "agent", text: reply.answer, typed: false }]);
    } finally {
      setSending(false);
    }
  }

  function markTyped(index: number) {
    setMessages((m) => m.map((msg, i) => (i === index ? { ...msg, typed: true } : msg)));
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }

  return (
    <aside className="flex flex-col gap-4 lg:w-80 shrink-0">
      <div className="bg-bg rounded-hig border border-separator border-l-[3px] border-l-tint-pink shadow-card p-4 animate-fade-in-up">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-5 h-5 rounded-full bg-tint-pink flex items-center justify-center shrink-0">
            <Icon name="pulse" className="w-3 h-3 text-white" />
          </span>
          <span className="text-footnote font-semibold uppercase text-tint-pink">AI suggestion</span>
        </div>
        {topRecommendation ? (
          <>
            <p className="text-body">{topRecommendation.problem}</p>
            <p className="text-footnote text-label-secondary mt-1">
              {topRecommendation.resource} · {topRecommendation.requiredAuthority} approval
            </p>
            <Link
              href={`/recommendations/${topRecommendation.id}`}
              className="text-footnote text-tint-blue mt-2 inline-flex items-center gap-0.5 group"
            >
              Review full recommendation
              <Icon name="chevronRight" className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </>
        ) : (
          <p className="text-body text-label-secondary flex items-center gap-2">
            <Icon name="checkCircle" className="w-4.5 h-4.5 text-tint-green" />
            No pending recommendations right now.
          </p>
        )}
      </div>

      <div className="bg-bg rounded-hig border border-separator shadow-card flex flex-col flex-1 min-h-[20rem] animate-fade-in-up [animation-delay:60ms]">
        <div className="px-4 py-3 border-b border-separator text-footnote text-label-secondary uppercase flex items-center gap-1.5">
          <Icon name="pulse" className="w-3.5 h-3.5 text-tint-pink" />
          Ask about this
        </div>
        <div ref={scrollRef} className="flex-1 flex flex-col gap-2 p-4 overflow-y-auto max-h-80 scroll-smooth">
          {messages.length === 0 && (
            <p className="text-footnote text-label-tertiary">
              Ask why this is happening, what the alternatives are, or whether it's safe.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`text-body rounded-hig px-3 py-2 max-w-[85%] shadow-card ${
                m.role === "user" ? "bg-tint-blue text-white self-end animate-slide-in-right" : "bg-bg-secondary text-label self-start animate-slide-in-left"
              }`}
            >
              {m.role === "agent" && !m.typed ? (
                <TypewriterText text={m.text} onDone={() => markTyped(i)} />
              ) : (
                m.text
              )}
            </div>
          ))}
          {sending && (
            <div className="flex items-center gap-1 self-start bg-bg-secondary rounded-hig px-3 py-2.5 animate-fade-in">
              <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot" />
              <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot [animation-delay:0.15s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot [animation-delay:0.3s]" />
            </div>
          )}
        </div>
        <form onSubmit={onSubmit} className="p-3 border-t border-separator flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question…"
            className="flex-1 text-body bg-bg-secondary rounded-hig px-3 min-h-[2.25rem] border border-separator outline-none transition-hig focus:border-tint-pink focus:ring-2 focus:ring-tint-pink-wash"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            aria-label="Send"
            className="w-9 h-9 shrink-0 flex items-center justify-center rounded-hig bg-tint-pink text-white disabled:opacity-40 enabled:hover:shadow-card-hover active:opacity-70 active:scale-90 transition-hig"
          >
            <Icon name="chevronRight" className="w-4.5 h-4.5" />
          </button>
        </form>
      </div>
    </aside>
  );
}
