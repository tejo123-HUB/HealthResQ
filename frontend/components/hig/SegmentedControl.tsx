"use client";

import { useLayoutEffect, useRef, useState } from "react";

/** iOS-style segmented control with a real sliding pill behind the active label (measured off the
 * actual button positions, not just an instant class swap) — the small physical motion is what
 * makes switching tabs read as "the same control, different state" rather than "a new screen". */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef<Map<T, HTMLButtonElement>>(new Map());
  const [pillStyle, setPillStyle] = useState<{ left: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const container = containerRef.current;
    const button = buttonRefs.current.get(value);
    if (!container || !button) return;
    const containerRect = container.getBoundingClientRect();
    const buttonRect = button.getBoundingClientRect();
    setPillStyle({ left: buttonRect.left - containerRect.left, width: buttonRect.width });
  }, [value, options.length]);

  return (
    <div ref={containerRef} className="relative inline-flex bg-bg-tertiary rounded-hig p-1 gap-1">
      {pillStyle && (
        <span
          aria-hidden="true"
          className="absolute top-1 bottom-1 bg-bg rounded-[9px] shadow-sm transition-[left,width] duration-[260ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
          style={{ left: pillStyle.left, width: pillStyle.width }}
        />
      )}
      {options.map((opt) => (
        <button
          key={opt.value}
          ref={(el) => {
            if (el) buttonRefs.current.set(opt.value, el);
            else buttonRefs.current.delete(opt.value);
          }}
          onClick={() => onChange(opt.value)}
          className={`relative z-10 transition-hig text-subhead font-medium rounded-[9px] px-3 min-h-[32px] ${
            value === opt.value ? "text-label" : "text-label-secondary hover:text-label"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
