"use client";

import { useMemo, useState } from "react";
import { Icon } from "@/components/hig/Icon";

export type Column<Row> = {
  key: string;
  label: string;
  align?: "left" | "right";
  /** Value used for sorting and, by default, display. */
  value: (row: Row) => number | string;
  /** Override just the rendered cell — sorting still uses `value`. */
  render?: (row: Row) => React.ReactNode;
};

/** A real table, not a stack of `ListRow`s pretending to be one: sticky header so column labels
 * stay visible while scrolling, click-to-sort per column (the sort itself is the primary way to
 * find "what needs attention" in a list too long to scan by eye), and a horizontal scroll
 * container so it never forces the page itself to scroll sideways on narrow viewports. Built for
 * lists that can run into the hundreds of rows (resource explorer, hundreds of facility-product
 * combinations) — a flat list of text rows stops being legible well before that. */
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
  const [sortKey, setSortKey] = useState(defaultSortKey ?? columns[0]?.key);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultSortDir);

  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sortKey);
    if (!col) return rows;
    const withKeys = rows.map((r) => ({ r, v: col.value(r) }));
    withKeys.sort((a, b) => {
      if (typeof a.v === "number" && typeof b.v === "number") return a.v - b.v;
      return String(a.v).localeCompare(String(b.v));
    });
    if (sortDir === "desc") withKeys.reverse();
    return withKeys.map((w) => w.r);
  }, [rows, columns, sortKey, sortDir]);

  function toggleSort(key: string) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const TONE_BAR: Record<string, string> = {
    default: "before:bg-transparent",
    warning: "before:bg-tint-orange",
    critical: "before:bg-tint-red",
  };

  return (
    <div className="bg-bg rounded-hig border border-separator shadow-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-callout border-collapse">
          <thead className="sticky top-0 bg-bg-secondary z-10">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className={`px-3.5 py-2 text-footnote font-semibold text-label-secondary uppercase cursor-pointer select-none whitespace-nowrap transition-hig hover:text-label ${
                    col.align === "right" ? "text-right" : "text-left"
                  }`}
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
          </thead>
          <tbody className="divide-y divide-separator">
            {sorted.map((row) => {
              const tone = rowTone?.(row) ?? "default";
              return (
                <tr
                  key={row.id}
                  className={`relative before:absolute before:left-0 before:top-0 before:bottom-0 before:w-[3px] transition-hig hover:bg-fill-thin ${TONE_BAR[tone]}`}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-3.5 py-2 tabular-nums whitespace-nowrap ${col.align === "right" ? "text-right" : "text-left"}`}
                    >
                      {col.render ? col.render(row) : col.value(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3.5 py-6 text-center text-footnote text-label-tertiary">
                  No rows yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
