"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, StatCard } from "@/components/hig/Card";
import { Combobox } from "@/components/hig/Combobox";
import { type Column, DataTable } from "@/components/hig/DataTable";
import { SegmentedControl } from "@/components/hig/SegmentedControl";
import { intelligence } from "@/lib/api/intelligence";
import type { Facility, Product, ResourceExplorerFacilityRow } from "@/lib/api/types";

type Mode = "OVERVIEW" | "FULL";
type Row = ResourceExplorerFacilityRow & { id: string; facilityName: string };

const CHART_LIMIT = 8;

/** INT-13's resource explorer, generalized for a catalog that can run into the hundreds of
 * products rather than a fixed handful: a searchable `Combobox` instead of a row of pills, and
 * two ways to look at the result per the progressive-disclosure pattern most data-table/dashboard
 * guidance converges on (start high-level, drill down on demand) — "Overview" surfaces only
 * facilities that actually have a deficit, with a bar chart making the worst ones visible at a
 * glance; "Full data" is the complete, sortable table for every facility in scope. Both modes
 * read the same streamed rows (`intelligence.streamResourceExplorer`) — the backend computes one
 * facility's forecast at a time and this renders each as it arrives, rather than showing a blank
 * screen for however long the last facility in scope takes to fit a model. */
export function ResourceExplorer({ products, facilities }: { products: Product[]; facilities: Facility[] }) {
  const [productId, setProductId] = useState<string | null>(products[0]?.id ?? null);
  const [mode, setMode] = useState<Mode>("OVERVIEW");
  const [rows, setRows] = useState<Row[]>([]);
  const [summary, setSummary] = useState<{ totalCurrentStock: number; totalDeficit: number } | null>(null);
  const [streaming, setStreaming] = useState(false);

  const facilityName = (facilityId: string) => facilities.find((f) => f.id === facilityId)?.name ?? facilityId;

  useEffect(() => {
    if (!productId) return;
    const controller = new AbortController();
    setRows([]);
    setSummary(null);
    setStreaming(true);

    (async () => {
      try {
        for await (const event of intelligence.streamResourceExplorer(productId, controller.signal)) {
          if (event.type === "facility") {
            const { type: _type, ...row } = event;
            setRows((prev) => [...prev, { ...row, id: row.facilityId, facilityName: facilityName(row.facilityId) }]);
          } else {
            setSummary({ totalCurrentStock: event.totalCurrentStock, totalDeficit: event.totalDeficit });
          }
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) throw err;
      } finally {
        setStreaming(false);
      }
    })();

    return () => controller.abort();
    // Re-run only when the selected resource changes — `facilityName` is stable enough per
    // render that including it would restart the stream on every unrelated re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const deficitRows = [...rows].filter((r) => r.deficit > 0).sort((a, b) => b.deficit - a.deficit);
  const chartRows = deficitRows.slice(0, CHART_LIMIT);
  const visibleRows = mode === "OVERVIEW" ? deficitRows : rows;

  const columns: Column<Row>[] = [
    { key: "facility", label: "Facility", value: (r) => r.facilityName },
    { key: "currentStock", label: "Stock", align: "right", value: (r) => Math.round(r.currentStock) },
    { key: "forecastDemand", label: "Demand", align: "right", value: (r) => Math.round(r.forecastDemand) },
    ...(mode === "FULL"
      ? [{ key: "projectedStock", label: "Projected", align: "right" as const, value: (r: Row) => Math.round(r.projectedStock) }]
      : []),
    {
      key: "deficit",
      label: "Deficit",
      align: "right",
      value: (r) => Math.round(r.deficit),
      render: (r) => (
        <span className={r.deficit > 0 ? "text-tint-red font-semibold" : "text-label-secondary"}>
          {Math.round(r.deficit)}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        {products.length > 0 && (
          <Combobox
            value={productId}
            onChange={setProductId}
            options={products.map((p) => ({ value: p.id, label: p.name }))}
            placeholder="Search resources…"
          />
        )}
        <SegmentedControl
          value={mode}
          onChange={setMode}
          options={[
            { value: "OVERVIEW", label: "Overview" },
            { value: "FULL", label: "Full data" },
          ]}
        />
      </div>

      {streaming && (
        <p className="text-footnote text-label-secondary flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot" />
          <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot [animation-delay:0.15s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot [animation-delay:0.3s]" />
          Computing forecasts… {rows.length}
          {facilities.length ? ` of ${facilities.length}` : ""} facilities
        </p>
      )}

      {mode === "OVERVIEW" && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatCard icon="building" label="Facilities in scope" numericValue={rows.length} tone="brown" />
            <StatCard
              icon="alert"
              label="Facilities with a deficit"
              numericValue={deficitRows.length}
              tone={deficitRows.length > 0 ? "warning" : "default"}
            />
            <StatCard icon="box" label="Total deficit" numericValue={summary?.totalDeficit} tone="pink" loading={!summary} />
          </div>

          {chartRows.length > 0 && (
            <Card>
              <p className="text-footnote text-label-secondary uppercase mb-3">
                Largest deficits
                {deficitRows.length > CHART_LIMIT ? ` (top ${CHART_LIMIT} of ${deficitRows.length})` : ""}
              </p>
              <ResponsiveContainer width="100%" height={Math.max(160, chartRows.length * 34)}>
                <BarChart data={chartRows} layout="vertical" margin={{ left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--separator)" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="facilityName" width={90} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="deficit" fill="var(--tint-red)" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {!streaming && deficitRows.length === 0 && rows.length > 0 && (
            <Card>
              <p className="text-body text-label-secondary text-center py-2">
                No deficits — every facility in scope has enough stock to cover its forecast demand.
              </p>
            </Card>
          )}
        </>
      )}

      <DataTable
        rows={visibleRows}
        columns={columns}
        defaultSortKey="deficit"
        rowTone={(r) => (r.deficit > 0 ? "warning" : "default")}
      />
    </div>
  );
}
