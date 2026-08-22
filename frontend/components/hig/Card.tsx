"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { Icon } from "@/components/hig/Icon";
import { Skeleton } from "@/components/hig/Skeleton";
import { useCountUp } from "@/lib/hooks/useCountUp";

export function Card({
  children,
  className = "",
  interactive = false,
}: {
  children: ReactNode;
  className?: string;
  /** Lifts on hover/press — use for a card that's a tap target (not a purely informational one),
   * so the elevation change itself signals "this responds to you". */
  interactive?: boolean;
}) {
  return (
    <div
      className={`bg-bg rounded-hig border border-separator p-3 shadow-card transition-hig ${
        interactive ? "hover:-translate-y-0.5 hover:shadow-card-hover active:translate-y-0 active:shadow-card cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}

/** A number is easy to glance past — pairing it with an icon and a plain-language label makes the
 * card recognizable without reading the number first. `tone` tints the icon, the value, and a
 * thin accent bar along the card's top edge when something needs attention. `index` staggers this
 * card's entrance animation when rendered in a grid, so a row of stat cards cascades in rather
 * than popping in all at once. Pass `numericValue` (rather than a pre-formatted `value`) for any
 * live figure that should visibly count up/down when it changes on refetch, instead of just
 * snapping to the new number. */
export function StatCard({
  icon,
  label,
  value,
  numericValue,
  tone = "default",
  href,
  loading = false,
  index = 0,
}: {
  icon: Parameters<typeof Icon>[0]["name"];
  label: string;
  value?: ReactNode;
  numericValue?: number;
  tone?: "default" | "warning" | "accent" | "pink" | "yellow" | "brown";
  href?: string;
  loading?: boolean;
  index?: number;
}) {
  const tweened = useCountUp(numericValue);
  const displayValue = numericValue !== undefined ? Math.round(tweened ?? numericValue).toLocaleString() : value;

  const TONE_TEXT: Record<string, string> = {
    default: "text-label",
    warning: "text-tint-orange",
    accent: "text-tint-blue",
    pink: "text-tint-pink",
    yellow: "text-tint-yellow",
    brown: "text-tint-brown",
  };
  const TONE_WASH: Record<string, string> = {
    default: "bg-fill-regular text-label-secondary",
    warning: "bg-tint-orange-wash text-tint-orange",
    accent: "bg-tint-blue-wash text-tint-blue",
    pink: "bg-tint-pink-wash text-tint-pink",
    yellow: "bg-tint-yellow-wash text-tint-yellow",
    brown: "bg-tint-brown-wash text-tint-brown",
  };
  const TONE_BAR: Record<string, string> = {
    default: "bg-transparent",
    warning: "bg-tint-orange",
    accent: "bg-tint-blue",
    pink: "bg-tint-pink",
    yellow: "bg-tint-yellow",
    brown: "bg-tint-brown",
  };
  const style: CSSProperties = { animationDelay: `${index * 60}ms` };

  const content = (
    <Card interactive={!!href} className="h-full relative overflow-hidden !p-0">
      <span className={`absolute top-0 left-0 right-0 h-[3px] ${TONE_BAR[tone]} transition-hig`} />
      <div className="p-3">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center mb-2 ${TONE_WASH[tone]}`}>
          <Icon name={icon} className="w-4 h-4" />
        </div>
        <p className="text-caption1 text-label-secondary">{label}</p>
        {loading ? (
          <Skeleton className="h-5 w-16 mt-1.5" />
        ) : (
          <p className={`text-title3 mt-0.5 tabular-nums ${TONE_TEXT[tone]}`}>{displayValue}</p>
        )}
      </div>
    </Card>
  );

  return (
    <div className="animate-fade-in-up" style={style}>
      {href ? <Link href={href}>{content}</Link> : content}
    </div>
  );
}

/** iOS-style inset grouped list container. */
export function ListGroup({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <div className="mb-6 animate-fade-in-up">
      {title && <div className="text-footnote text-label-secondary px-4 mb-1 uppercase">{title}</div>}
      <div className="bg-bg rounded-hig border border-separator shadow-card divide-y divide-separator overflow-hidden">
        {children}
      </div>
    </div>
  );
}

export function ListRow({
  label,
  value,
  onClick,
}: {
  label: ReactNode;
  value?: ReactNode;
  onClick?: () => void;
}) {
  const interactive = Boolean(onClick);
  return (
    <div
      onClick={onClick}
      className={`flex items-center justify-between px-3.5 min-h-[2.375rem] py-1.5 transition-hig ${
        interactive ? "cursor-pointer hover:bg-fill-thin active:bg-fill-regular active:scale-[0.99]" : ""
      }`}
    >
      <span className="text-callout">{label}</span>
      {value !== undefined && <span className="text-callout text-label-secondary tabular-nums">{value}</span>}
    </div>
  );
}
