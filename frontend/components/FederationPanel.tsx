"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { Card, ListGroup, ListRow, StatCard } from "@/components/hig/Card";
import { Icon } from "@/components/hig/Icon";
import { SegmentedControl } from "@/components/hig/SegmentedControl";
import { federation } from "@/lib/api/federation";
import type { FederationCountryRow } from "@/lib/api/types";

type SortMetric = "demandTrend" | "volatility" | "stockoutFrequency";

/** iOS-standard "hide everything except the marked subtree" print recipe, injected locally rather
 * than in the shared stylesheet (this component is the only one that owns a presentation/export
 * mode). `!important` is required: the descendant re-visibility rule below it would otherwise win
 * on specificity for elements inside `#federation-print-root`. */
const PRINT_STYLES = `
@media print {
  body * { visibility: hidden; }
  #federation-print-root, #federation-print-root * { visibility: visible; }
  #federation-print-root {
    position: absolute;
    inset: 0;
    width: 100%;
    padding: 24px;
    font-size: 1.15em;
  }
  #federation-print-root .federation-no-print { display: none !important; }
}
`;

/** INT-11: five synthetic BRICS datasets. The "Federation" tab of the National workspace. */
export function FederationPanel() {
  const { t } = useTranslation("dashboard");
  const { data: rows } = useSWR(["federation"], () => federation.getProfile());
  const [metric, setMetric] = useState<SortMetric>("demandTrend");
  const [presentation, setPresentation] = useState(false);

  const METRIC_OPTIONS: { value: SortMetric; label: string }[] = [
    { value: "demandTrend", label: t("federation.demandTrend") },
    { value: "volatility", label: t("federation.volatility") },
    { value: "stockoutFrequency", label: t("federation.stockouts") },
  ];

  const sortedRows = useMemo<FederationCountryRow[] | undefined>(
    () => (rows ? [...rows].sort((a, b) => b[metric] - a[metric]) : rows),
    [rows, metric]
  );

  return (
    <div id="federation-print-root" className="flex flex-col gap-6">
      <style>{PRINT_STYLES}</style>

      <div className="flex items-center justify-end federation-no-print">
        <button
          type="button"
          onClick={() => setPresentation((p) => !p)}
          aria-pressed={presentation}
          className="text-footnote font-medium text-label-secondary hover:text-label rounded-hig px-3 py-1.5 border border-separator transition-hig"
        >
          {presentation ? t("federation.exitPresentationMode") : t("federation.presentationMode")}
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          icon="flag"
          label={t("federation.participatingCountries")}
          numericValue={rows?.length}
          value={rows ? undefined : "—"}
          tone="pink"
        />
        <StatCard icon="refresh" label={t("federation.latestRound")} value={rows?.[0]?.latestRound ?? "—"} tone="yellow" />
        <Card className="col-span-2">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full flex items-center justify-center bg-fill-regular text-label-secondary shrink-0">
              <Icon name="lock" className="w-3.5 h-3.5" />
            </span>
            <p className="text-caption1 text-label-secondary">{t("federation.rawRecordsShared")}</p>
          </div>
          <p className="text-title3 mt-1 text-label">0</p>
          <p className="text-footnote text-label-secondary mt-1">{t("federation.structuralGuaranteeNote")}</p>
        </Card>
      </div>

      {sortedRows && sortedRows.length > 0 && (
        <Card>
          <p className="text-footnote text-label-secondary uppercase mb-3">{t("federation.demandTrendByRound")}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {sortedRows.map((r) => (
              <div key={r.country} className="rounded-hig border border-separator p-2">
                <p className={`text-caption1 text-label-secondary mb-1 ${presentation ? "text-footnote" : ""}`}>
                  {r.country}
                </p>
                <ResponsiveContainer width="100%" height={presentation ? 140 : 110}>
                  <LineChart data={r.demandTrendSeries} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--separator)" />
                    <XAxis
                      dataKey="round"
                      tickFormatter={(v) => t("federation.roundShort", { n: v })}
                      tick={{ fontSize: presentation ? 12 : 10 }}
                    />
                    <YAxis tick={{ fontSize: presentation ? 12 : 10 }} width={32} />
                    <Tooltip
                      labelFormatter={(v) => t("federation.round", { n: v })}
                      formatter={(value: number) => [value.toFixed(2), t("federation.demandTrend")]}
                    />
                    <Line
                      type="monotone"
                      dataKey="demandTrend"
                      stroke="var(--tint-orange)"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="federation-no-print">
        <SegmentedControl options={METRIC_OPTIONS} value={metric} onChange={setMetric} />
      </div>

      <ListGroup title={t("federation.countryComparisonDescending")}>
        {sortedRows?.map((r) => (
          <ListRow
            key={r.country}
            label={
              <span className={presentation ? "text-title3" : undefined}>
                {t("federation.countryParticipants", { country: r.country, n: r.participants })}
              </span>
            }
            value={
              <span className={presentation ? "text-body" : undefined}>
                {t("federation.countryMetrics", {
                  trend: r.demandTrend.toFixed(2),
                  volatility: r.volatility.toFixed(2),
                  stockoutPct: (r.stockoutFrequency * 100).toFixed(0),
                })}
              </span>
            }
          />
        ))}
      </ListGroup>
    </div>
  );
}
