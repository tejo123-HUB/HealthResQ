"use client";

import useSWR from "swr";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, ListGroup, ListRow, StatCard } from "@/components/hig/Card";
import { federation } from "@/lib/api/federation";

/** INT-11: five synthetic BRICS datasets. The "Federation" tab of the National workspace. */
export function FederationPanel() {
  const { data: rows } = useSWR(["federation"], () => federation.getProfile());

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard icon="flag" label="Participating countries" numericValue={rows?.length} value={rows ? undefined : "—"} />
        <StatCard icon="refresh" label="Latest round" value={rows?.[0]?.latestRound ?? "—"} />
        <Card className="col-span-2">
          <p className="text-caption1 text-label-secondary">Raw PHC-level records shared</p>
          <p className="text-title2 mt-1 text-tint-green animate-pop-in">0</p>
          <p className="text-footnote text-label-secondary mt-1">
            Structural guarantee (INT-10): only the eleven documented aggregate fields ever leave a
            national node — never raw facility or patient data.
          </p>
        </Card>
      </div>

      {rows && (
        <Card>
          <p className="text-footnote text-label-secondary uppercase mb-3">Demand trend by country</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--separator)" />
              <XAxis dataKey="country" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="demandTrend" fill="var(--tint-blue)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      <ListGroup title="Country comparison">
        {rows?.map((r) => (
          <ListRow
            key={r.country}
            label={`${r.country} · ${r.participants} participants`}
            value={`trend ${r.demandTrend.toFixed(2)} · volatility ${r.volatility.toFixed(2)} · stockout freq ${(r.stockoutFrequency * 100).toFixed(0)}%`}
          />
        ))}
      </ListGroup>
    </div>
  );
}
