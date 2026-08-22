"use client";

import { useState, type ReactNode } from "react";
import { Icon } from "@/components/hig/Icon";

/** Collapsed-by-default reveal for secondary content that shouldn't compete with the primary
 * flow at a glance — demo-account credentials on Login, a recommendation's "Why"/"Evidence"
 * detail. Uncontrolled by default (`defaultOpen`); pass `open`/`onOpenChange` to control it. */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
  open: openProp,
  onOpenChange,
  className = "",
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
}) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const open = openProp ?? uncontrolledOpen;

  const toggle = () => {
    if (onOpenChange) onOpenChange(!open);
    else setUncontrolledOpen(!open);
  };

  return (
    <div className={className}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-footnote text-label-secondary hover:text-label transition-hig"
      >
        <Icon name="chevronDown" className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
        {summary}
      </button>
      {open && <div className="animate-fade-in-up mt-2">{children}</div>}
    </div>
  );
}
