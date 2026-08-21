import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { Icon } from "@/components/hig/Icon";
import { Skeleton } from "@/components/hig/Skeleton";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-bg rounded-hig border border-separator p-4 ${className}`}>{children}</div>
  );
}

/** A number is easy to glance past — pairing it with an icon and a plain-language label makes the
 * card recognizable without reading the number first. `tone` tints the icon and (optionally) the
 * value when something needs attention. `index` staggers this card's entrance animation when
 * rendered in a grid, so a row of stat cards cascades in rather than popping in all at once. */
export function StatCard({
  icon,
  label,
  value,
  tone = "default",
  href,
  loading = false,
  index = 0,
}: {
  icon: Parameters<typeof Icon>[0]["name"];
  label: string;
  value: ReactNode;
  tone?: "default" | "warning" | "accent";
  href?: string;
  loading?: boolean;
  index?: number;
}) {
  const toneClasses =
    tone === "warning" ? "text-tint-orange" : tone === "accent" ? "text-tint-blue" : "text-label";
  const iconWashClasses =
    tone === "warning" ? "bg-tint-orange-wash text-tint-orange" : tone === "accent" ? "bg-tint-blue-wash text-tint-blue" : "bg-fill-regular text-label-secondary";
  const style: CSSProperties = { animationDelay: `${index * 60}ms` };

  const content = (
    <Card className={`h-full animate-fade-in-up ${href ? "active:opacity-70 active:scale-[0.98] transition-hig" : ""}`}>
      <div className={`w-9 h-9 rounded-full flex items-center justify-center mb-2 ${iconWashClasses}`}>
        <Icon name={icon} className="w-4.5 h-4.5" />
      </div>
      <p className="text-caption1 text-label-secondary">{label}</p>
      {loading ? (
        <Skeleton className="h-6 w-16 mt-1.5" />
      ) : (
        <p className={`text-title2 mt-0.5 ${toneClasses}`}>{value}</p>
      )}
    </Card>
  );

  if (href) {
    return (
      <div style={style}>
        <Link href={href}>{content}</Link>
      </div>
    );
  }
  return <div style={style}>{content}</div>;
}

/** iOS-style inset grouped list container. */
export function ListGroup({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <div className="mb-6 animate-fade-in-up">
      {title && <div className="text-footnote text-label-secondary px-4 mb-1 uppercase">{title}</div>}
      <div className="bg-bg rounded-hig border border-separator divide-y divide-separator overflow-hidden">
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
      className={`flex items-center justify-between px-4 min-h-[44px] py-2 transition-hig ${
        interactive ? "cursor-pointer active:bg-fill-regular active:scale-[0.99]" : ""
      }`}
    >
      <span className="text-body">{label}</span>
      {value !== undefined && <span className="text-body text-label-secondary">{value}</span>}
    </div>
  );
}
