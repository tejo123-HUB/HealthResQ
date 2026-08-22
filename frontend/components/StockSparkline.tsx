"use client";

// OPS-06/Phase 8: there is no real historical stock series anywhere in this app
// (`InventoryTransaction` has a write-only path with no code path populating it in normal
// operation) — so this renders the forward-looking 14-day projection from
// `intelligence.getForecastPoints` instead ("projected stock, next 14 days"), reusing the
// ForecastPoint rows the risk-map alert pipeline already computes. Always rendered directly
// (never behind a `:hover`-only reveal), so it reads the same on a touch device as on desktop.

import useSWR from "swr";
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { intelligence } from "@/lib/api/intelligence";
import { formatNumber } from "@/lib/i18n/format";
import type { ForecastPointSeries } from "@/lib/api/types";

const EMPTY_SERIES = (facilityId: string, productId: string): ForecastPointSeries => ({
  facilityId,
  productId,
  points: [],
});

export function StockSparkline({
  facilityId,
  productId,
  height = 48,
}: {
  facilityId: string;
  productId: string;
  height?: number;
}) {
  const { t, i18n } = useTranslation("dashboard");
  const { data, isLoading } = useSWR(["forecast-points", facilityId, productId], () =>
    // A facility+product pair with no forecast computed yet (see caveat in the risk-map read
    // path) 404s here — that's "no projection available", not a fetch failure, so it's swallowed
    // into an empty series rather than surfaced as an error.
    intelligence.getForecastPoints(facilityId, productId).catch(() => EMPTY_SERIES(facilityId, productId))
  );

  if (isLoading) {
    return <div className="rounded-hig bg-fill-thin animate-pulse" style={{ height }} />;
  }

  const points = data?.points ?? [];
  if (points.length === 0) {
    return <p className="text-caption2 text-label-tertiary italic">{t("dashboard:sparkline.noProjection")}</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Tooltip
          formatter={(value: number) => [formatNumber(Math.round(value), i18n.language), t("dashboard:sparkline.projectedStock")]}
          labelFormatter={(dayOffset: number) => t("dashboard:sparkline.dayOffset", { n: dayOffset })}
          contentStyle={{ fontSize: 11 }}
        />
        <Line type="monotone" dataKey="point" stroke="var(--tint-blue)" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line
          type="monotone"
          dataKey="low"
          stroke="var(--separator)"
          strokeWidth={1}
          strokeDasharray="3 3"
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="high"
          stroke="var(--separator)"
          strokeWidth={1}
          strokeDasharray="3 3"
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
