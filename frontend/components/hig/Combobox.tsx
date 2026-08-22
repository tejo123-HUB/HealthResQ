"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/hig/Icon";

/** Type-to-filter picker for a list too long to render as a row of pills (`SegmentedControl` is
 * fine for 3-6 fixed tabs; a resource catalog can run into the hundreds). Shows the current
 * selection as a closed button; opening it reveals a search box and a scrollable, filtered list —
 * the standard combobox pattern, generalized so it works for any option list, not just products. */
export function Combobox<T extends string>({
  options,
  value,
  onChange,
  placeholder = "Search…",
}: {
  options: { value: T; label: string }[];
  value: T | null;
  onChange: (v: T) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = options.find((o) => o.value === value);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery("");
      // Focus after the panel mounts, not on the same tick as the click that opened it.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  function select(v: T) {
    onChange(v);
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative w-full sm:max-w-xs">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 text-body bg-bg-secondary rounded-hig px-3 min-h-[2.375rem] border border-separator transition-hig hover:bg-fill-thin"
      >
        <span className="truncate">{selected?.label ?? "Select…"}</span>
        <Icon name="chevronDown" className={`w-4 h-4 shrink-0 text-label-secondary transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute z-20 mt-1.5 w-full bg-bg rounded-hig border border-separator shadow-popover overflow-hidden animate-scale-in origin-top">
          <div className="flex items-center gap-2 px-3 border-b border-separator">
            <Icon name="search" className="w-4 h-4 text-label-tertiary shrink-0" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={placeholder}
              className="flex-1 text-body bg-transparent py-2.5 outline-none"
            />
          </div>
          <div className="max-h-64 overflow-y-auto py-1">
            {filtered.length === 0 && (
              <p className="px-3 py-2.5 text-footnote text-label-tertiary">No matches.</p>
            )}
            {filtered.map((o) => (
              <button
                key={o.value}
                type="button"
                onClick={() => select(o.value)}
                className={`w-full flex items-center justify-between gap-2 text-left text-body px-3 py-2 transition-hig hover:bg-fill-thin ${
                  o.value === value ? "text-tint-blue" : "text-label"
                }`}
              >
                <span className="truncate">{o.label}</span>
                {o.value === value && <Icon name="check" className="w-4 h-4 shrink-0" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
