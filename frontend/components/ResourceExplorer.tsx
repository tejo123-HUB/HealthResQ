"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { Card, StatCard } from "@/components/hig/Card";
import { Combobox } from "@/components/hig/Combobox";
import { Icon } from "@/components/hig/Icon";
import { type Column, DataTable } from "@/components/hig/DataTable";
import { SegmentedControl } from "@/components/hig/SegmentedControl";
import { intelligence } from "@/lib/api/intelligence";
import type { Facility, Product, ResourceExplorerFacilityRow } from "@/lib/api/types";

type Mode = "OVERVIEW" | "FULL";
type Row = ResourceExplorerFacilityRow & { id: string; facilityName: string };

const CHART_LIMIT = 8;

/** Deficit-magnitude severity tiers for the overview chart. There's no backend-computed severity
 * for the resource explorer's per-facility deficit (that concept only exists elsewhere, keyed off
 * days-to-stockout — a field this endpoint doesn't return), so tiers are derived here as fractions
 * of the largest deficit currently shown (the chart already caps at the worst `CHART_LIMIT`
 * facilities, so "largest visible deficit" is a reasonable, self-relative scale). WATCH is the
 * boundary the `ReferenceLine` marks — bars short of it stay a muted neutral; everything at or
 * past it is colored by tier using the Phase 1 tokens (amber/orange/red, distinct hues). */
const WATCH_FRACTION = 0.25;
const HIGH_FRACTION = 0.5;
const CRITICAL_FRACTION = 0.75;

function severityFill(deficit: number, maxDeficit: number): string {
  if (maxDeficit <= 0) return "var(--separator)";
  if (deficit >= maxDeficit * CRITICAL_FRACTION) return "var(--tint-red)";
  if (deficit >= maxDeficit * HIGH_FRACTION) return "var(--tint-orange)";
  if (deficit >= maxDeficit * WATCH_FRACTION) return "var(--tint-amber)";
  return "var(--separator)";
}

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
  const { t } = useTranslation("dashboard");
  const [productId, setProductId] = useState<string | null>(products[0]?.id ?? null);
  const [mode, setMode] = useState<Mode>("OVERVIEW");
  const [rows, setRows] = useState<Row[]>([]);
  const [summary, setSummary] = useState<{ totalCurrentStock: number; totalDeficit: number } | null>(null);
  const [streaming, setStreaming] = useState(false);
  // Clicking a bar in the Overview chart "zooms in" to that one facility's row in Full Data mode,
  // rather than feeling like a jump to an unrelated screen — a clearable chip shows what's
  // filtered and lets the user get back to every row without leaving Full Data mode.
  const [selectedFacilityId, setSelectedFacilityId] = useState<string | null>(null);
  // Which row currently has its forecast-uncertainty band expanded (on-demand only, per the spec
  // — never shown by default alongside every row).
  const [expandedRangeId, setExpandedRangeId] = useState<string | null>(null);

  const facilityName = (facilityId: string) => facilities.find((f) => f.id === facilityId)?.name ?? facilityId;

  useEffect(() => {
    if (!productId) return;
    const controller = new AbortController();
    setRows([]);
    setSummary(null);
    setStreaming(true);
    setSelectedFacilityId(null);
    setExpandedRangeId(null);

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
  const maxChartDeficit = chartRows.reduce((m, r) => Math.max(m, r.deficit), 0);
  const watchThreshold = maxChartDeficit * WATCH_FRACTION;
  const selectedFacilityName = selectedFacilityId ? facilityName(selectedFacilityId) : null;
  const baseVisibleRows = mode === "OVERVIEW" ? deficitRows : rows;
  const visibleRows =
    mode === "FULL" && selectedFacilityId ? baseVisibleRows.filter((r) => r.facilityId === selectedFacilityId) : baseVisibleRows;

  function selectFacilityFromChart(facilityId: string) {
    setSelectedFacilityId(facilityId);
    setMode("FULL");
  }

  function changeMode(next: Mode) {
    if (next === "OVERVIEW") setSelectedFacilityId(null);
    setMode(next);
  }

  const columns: Column<Row>[] = [
    { key: "facility", label: t("explorer.columns.facility"), value: (r) => r.facilityName },
    { key: "currentStock", label: t("explorer.columns.stock"), align: "right", value: (r) => Math.round(r.currentStock) },
    {
      key: "forecastDemand",
      label: t("explorer.columns.demand"),
      align: "right",
      value: (r) => Math.round(r.forecastDemand),
      render: (r) =>
        r.rangeLow != null && r.rangeHigh != null ? (
          <button
            type="button"
            onClick={() => setExpandedRangeId((id) => (id === r.id ? null : r.id))}
            className="inline-flex items-center gap-1 tabular-nums hover:text-tint-blue transition-hig"
            aria-expanded={expandedRangeId === r.id}
            title={t("explorer.showForecastCertainty")}
          >
            {Math.round(r.forecastDemand)}
            <Icon name="chevronDown" className={`w-3 h-3 transition-hig ${expandedRangeId === r.id ? "rotate-180" : ""}`} />
          </button>
        ) : (
          Math.round(r.forecastDemand)
        ),
    },
    ...(mode === "FULL"
      ? [
          {
            key: "projectedStock",
            label: t("explorer.columns.projected"),
            align: "right" as const,
            value: (r: Row) => Math.round(r.projectedStock),
          },
        ]
      : []),
    {
      key: "deficit",
      label: t("explorer.columns.deficit"),
      align: "right",
      value: (r) => Math.round(r.deficit),
      render: (r) => (
        <div>
          <span className={r.deficit > 0 ? "text-tint-red font-semibold" : "text-label-secondary"}>
            {Math.round(r.deficit)}
          </span>
          {expandedRangeId === r.id && r.rangeLow != null && r.rangeHigh != null && (
            <p className="mt-1 text-footnote font-normal text-label-tertiary whitespace-normal max-w-[180px] text-left ml-auto">
              {t("explorer.forecastUncertaintyNote")}
            </p>
          )}
        </div>
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
            placeholder={t("explorer.searchResources")}
          />
        )}
        <SegmentedControl
          value={mode}
          onChange={changeMode}
          options={[
            { value: "OVERVIEW", label: t("tabs.overview") },
            { value: "FULL", label: t("explorer.fullData") },
          ]}
        />
      </div>

      {streaming && (
        <p className="text-footnote text-label-secondary flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot" />
          <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot [animation-delay:0.15s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-label-tertiary animate-bounce-dot [animation-delay:0.3s]" />
          {facilities.length
            ? t("explorer.computingForecastsOf", { n: rows.length, total: facilities.length })
            : t("explorer.computingForecasts", { n: rows.length })}
        </p>
      )}

      {mode === "OVERVIEW" && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatCard icon="building" label={t("stats.facilitiesInScope")} numericValue={rows.length} tone="brown" />
            <StatCard
              icon="alert"
              label={t("explorer.facilitiesWithDeficit")}
              numericValue={deficitRows.length}
              tone={deficitRows.length > 0 ? "warning" : "default"}
            />
            <StatCard icon="box" label={t("stats.totalDeficit")} numericValue={summary?.totalDeficit} tone="pink" loading={!summary} />
          </div>

          {chartRows.length > 0 && (
            <Card>
              <p className="text-footnote text-label-secondary uppercase mb-3">
                {deficitRows.length > CHART_LIMIT
                  ? t("explorer.largestDeficitsOf", { limit: CHART_LIMIT, total: deficitRows.length })
                  : t("explorer.largestDeficits")}
              </p>
              <ResponsiveContainer width="100%" height={Math.max(160, chartRows.length * 34)}>
                <BarChart data={chartRows} layout="vertical" margin={{ left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--separator)" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="facilityName" width={90} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  {watchThreshold > 0 && (
                    <ReferenceLine
                      x={watchThreshold}
                      stroke="var(--label-tertiary)"
                      strokeDasharray="4 4"
                      label={{ value: t("severityWatchShort"), position: "insideTopRight", fontSize: 10, fill: "var(--label-tertiary)" }}
                    />
                  )}
                  <Bar
                    dataKey="deficit"
                    radius={[0, 6, 6, 0]}
                    cursor="pointer"
                    onClick={(data: unknown) => {
                      const payload = (data as { payload?: Row } | Row | undefined) ?? undefined;
                      const row = payload && "payload" in payload ? payload.payload : (payload as Row | undefined);
                      if (row?.facilityId) selectFacilityFromChart(row.facilityId);
                    }}
                  >
                    {chartRows.map((row) => (
                      <Cell
                        key={row.id}
                        fill={severityFill(row.deficit, maxChartDeficit)}
                        stroke={selectedFacilityId === row.facilityId ? "var(--tint-blue)" : "transparent"}
                        strokeWidth={selectedFacilityId === row.facilityId ? 2 : 0}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="text-footnote text-label-tertiary mt-2">{t("explorer.tapBarToZoom")}</p>
            </Card>
          )}

          {!streaming && deficitRows.length === 0 && rows.length > 0 && (
            <Card>
              <p className="text-body text-label-secondary text-center py-2">{t("explorer.noDeficits")}</p>
            </Card>
          )}
        </>
      )}

      {mode === "FULL" && selectedFacilityName && (
        <div className="flex items-center gap-1.5 self-start rounded-full bg-tint-blue-wash text-tint-blue pl-3 pr-1.5 py-1 text-footnote font-medium animate-fade-in-up">
          <span>{selectedFacilityName}</span>
          <button
            type="button"
            onClick={() => setSelectedFacilityId(null)}
            aria-label={t("explorer.clearFilter", { name: selectedFacilityName })}
            className="w-5 h-5 flex items-center justify-center rounded-full hover:bg-tint-blue-wash-strong active:scale-90 transition-hig"
          >
            <Icon name="x" className="w-3 h-3" />
          </button>
        </div>
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
