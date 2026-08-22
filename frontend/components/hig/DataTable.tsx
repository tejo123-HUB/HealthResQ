"use client";

import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Icon } from "@/components/hig/Icon";

export type Column<Row> = {
  key: string;
  label: string;
  align?: "left" | "right";
  /** Value used for sorting and, by default, display. */
  value: (row: Row) => number | string;
  /** Override just the rendered cell — sorting still uses `value`. */
  render?: (row: Row) => React.ReactNode;
  /** Set false to hide the per-column filter input for a column where substring matching on the
   * rendered value wouldn't mean anything (e.g. a column that's already just a formatted number
   * derived from another column). Defaults to filterable. */
  filterable?: boolean;
};

// Rows beyond this count switch from plain rendering to windowed rendering — small tables (the
// common case) stay exactly as before, so there's no virtualizer overhead or scroll-container
// change for the lists this was already tuned for.
const VIRTUALIZE_THRESHOLD = 50;
const ROW_HEIGHT_PX = 37; // measured from the existing px-3.5 py-2 + text-callout row
const VIRTUAL_MAX_HEIGHT_PX = 520;

/** A real table, not a stack of `ListRow`s pretending to be one: sticky header so column labels
 * stay visible while scrolling, click-to-sort per column (the sort itself is the primary way to
 * find "what needs attention" in a list too long to scan by eye), and a horizontal scroll
 * container so it never forces the page itself to scroll sideways on narrow viewports. Built for
 * lists that can run into the hundreds of rows (resource explorer, hundreds of facility-product
 * combinations) — a flat list of text rows stops being legible well before that. The first column
 * also stays pinned on horizontal scroll (facility/product name is the one thing every other cell
 * needs to be read against), each column carries its own substring filter, and row counts past
 * `VIRTUALIZE_THRESHOLD` are windowed with `@tanstack/react-virtual` so a hundreds-of-rows table
 * doesn't mean hundreds of live DOM rows. */
export function DataTable<Row extends { id: string }>({
  rows,
  columns,
  defaultSortKey,
  defaultSortDir = "desc",
  rowTone,
}: {
  rows: Row[];
  columns: Column<Row>[];
  defaultSortKey?: string;
  defaultSortDir?: "asc" | "desc";
  /** Optional per-row visual emphasis (e.g. a left accent bar) — used to make "needs attention"
   * rows findable at a glance, not just sortable to the top. */
  rowTone?: (row: Row) => "default" | "warning" | "critical";
}) {
  const { t } = useTranslation("common");
  const [sortKey, setSortKey] = useState(defaultSortKey ?? columns[0]?.key);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultSortDir);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const active = Object.entries(filters).filter(([, v]) => v.trim().length > 0);
    if (active.length === 0) return rows;
    return rows.filter((row) =>
      active.every(([key, needle]) => {
        const col = columns.find((c) => c.key === key);
        if (!col) return true;
        return String(col.value(row)).toLowerCase().includes(needle.trim().toLowerCase());
      })
    );
  }, [rows, columns, filters]);

  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sortKey);
    if (!col) return filtered;
    const withKeys = filtered.map((r) => ({ r, v: col.value(r) }));
    withKeys.sort((a, b) => {
      if (typeof a.v === "number" && typeof b.v === "number") return a.v - b.v;
      return String(a.v).localeCompare(String(b.v));
    });
    if (sortDir === "desc") withKeys.reverse();
    return withKeys.map((w) => w.r);
  }, [filtered, columns, sortKey, sortDir]);

  function toggleSort(key: string) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const virtualize = sorted.length > VIRTUALIZE_THRESHOLD;
  const rowVirtualizer = useVirtualizer({
    count: sorted.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 8,
    enabled: virtualize,
  });
  const virtualItems = virtualize ? rowVirtualizer.getVirtualItems() : [];
  const firstVirtual = virtualItems[0];
  const lastVirtual = virtualItems[virtualItems.length - 1];
  const topPad = firstVirtual ? firstVirtual.start : 0;
  const bottomPad = lastVirtual ? rowVirtualizer.getTotalSize() - lastVirtual.end : 0;
  const visibleRows = virtualize
    ? virtualItems.map((vi) => sorted[vi.index]).filter((r): r is Row => r != null)
    : sorted;

  // Rendered as a left border on the first (sticky) cell rather than a `::before` on the row: the
  // sticky column needs its own opaque background so scrolled content doesn't bleed through it,
  // which would otherwise paint over — and hide — a row-level accent bar sitting at the same
  // left edge.
  const TONE_BORDER: Record<string, string> = {
    default: "border-l-transparent",
    warning: "border-l-tint-orange",
    critical: "border-l-tint-red",
  };

  return (
    <div className="bg-bg rounded-hig border border-separator shadow-card overflow-hidden">
      <div
        ref={scrollRef}
        className="overflow-x-auto"
        style={virtualize ? { overflowY: "auto", maxHeight: VIRTUAL_MAX_HEIGHT_PX } : undefined}
      >
        <table className="w-full text-callout border-collapse">
          <thead className="sticky top-0 bg-bg-secondary z-10">
            <tr>
              {columns.map((col, i) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className={`px-3.5 py-2 text-footnote font-semibold text-label-secondary uppercase cursor-pointer select-none whitespace-nowrap transition-hig hover:text-label ${
                    col.align === "right" ? "text-right" : "text-left"
                  } ${i === 0 ? "sticky left-0 z-20 bg-bg-secondary" : ""}`}
                  title={col.label}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {sortKey === col.key && (
                      <Icon name={sortDir === "asc" ? "chevronRight" : "chevronDown"} className="w-3 h-3 -rotate-90" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
            <tr>
              {columns.map((col, i) => (
                <th
                  key={col.key}
                  className={`px-2 pb-2 bg-bg-secondary font-normal ${i === 0 ? "sticky left-0 z-20" : ""}`}
                >
                  {col.filterable === false ? null : (
                    <input
                      type="text"
                      value={filters[col.key] ?? ""}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => setFilters((f) => ({ ...f, [col.key]: e.target.value }))}
                      placeholder={t("filterPlaceholder")}
                      aria-label={t("filterColumn", { label: col.label })}
                      className={`w-full min-w-[64px] rounded-md border border-separator bg-bg px-2 py-1 text-footnote font-normal text-label placeholder:text-label-tertiary focus:outline-none focus:ring-2 focus:ring-tint-blue ${
                        col.align === "right" ? "text-right" : "text-left"
                      }`}
                    />
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-separator">
            {virtualize && topPad > 0 && (
              <tr aria-hidden style={{ height: topPad }}>
                <td colSpan={columns.length} className="p-0" />
              </tr>
            )}
            {visibleRows.map((row) => {
              const tone = rowTone?.(row) ?? "default";
              return (
                <tr key={row.id} className="group transition-hig hover:bg-fill-thin">
                  {columns.map((col, i) => (
                    <td
                      key={col.key}
                      className={`px-3.5 py-2 tabular-nums whitespace-nowrap ${col.align === "right" ? "text-right" : "text-left"} ${
                        i === 0
                          ? `sticky left-0 z-[1] bg-bg group-hover:bg-fill-thin border-l-[3px] ${TONE_BORDER[tone]}`
                          : ""
                      }`}
                      title={col.render ? undefined : String(col.value(row))}
                    >
                      {col.render ? col.render(row) : col.value(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
            {virtualize && bottomPad > 0 && (
              <tr aria-hidden style={{ height: bottomPad }}>
                <td colSpan={columns.length} className="p-0" />
              </tr>
            )}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3.5 py-6 text-center text-footnote text-label-tertiary">
                  {rows.length === 0 ? t("noRowsYet") : t("noRowsMatchFilters")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
