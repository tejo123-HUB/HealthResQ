"use client";

import Link from "next/link";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import useSWR from "swr";
import { AgentPane } from "@/components/agent/AgentPane";
import { FederationPanel } from "@/components/FederationPanel";
import { ListGroup, StatCard } from "@/components/hig/Card";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Icon } from "@/components/hig/Icon";
import { ProportionBar } from "@/components/hig/ProportionBar";
import { SegmentedControl } from "@/components/hig/SegmentedControl";
import { SeverityBadge, type Severity } from "@/components/hig/SeverityBadge";
import { ResourceExplorer } from "@/components/ResourceExplorer";
import { RiskMap } from "@/components/RiskMap";
import { intelligence } from "@/lib/api/intelligence";
import { ops } from "@/lib/api/ops";
import type { Scope, ScopeLevel } from "@/lib/api/types";

type Tab = "OVERVIEW" | "RISK_MAP" | "EXPLORER" | "FEDERATION";

/** CMD-09: District/State/National dashboards, each strictly scoped to the viewing user's own
 * authority level in the real implementation — one workspace per role, organized with tabs
 * (Federation only applies at NATIONAL) instead of separate nav destinations. Composing a new
 * action is a single icon button here rather than a persistent nav pill. Data lives in the main
 * column; the AI suggestion + chat side pane (AgentPane) is where it gets discussed — always
 * present, not a modal. Data comes from the real backend via lib/api/intelligence.ts (INT-13) and
 * lib/api/command.ts (CMD-09) — this component doesn't know or care which direction owns which
 * endpoint. */
export function DashboardScreen({ level, scopeId }: { level: ScopeLevel; scopeId: string }) {
  const { t } = useTranslation(["dashboard", "nav", "common"]);
  const [tab, setTab] = useState<Tab>("OVERVIEW");
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
    mutate: retrySummary,
  } = useSWR(["scope-summary", level], () => intelligence.getScopeSummary(level));
  // Only fetched while the matching tab is open — risk-map is cheap (reads persisted alerts);
  // the resource explorer's own data fetching (streamed, per-resource) lives in ResourceExplorer.
  const { data: markers } = useSWR(tab === "RISK_MAP" ? ["risk-markers"] : null, () => intelligence.getRiskMarkers());
  const { data: products } = useSWR(tab === "EXPLORER" ? ["products"] : null, () => ops.listProducts());
  const { data: facilities } = useSWR(tab === "EXPLORER" ? ["facilities"] : null, () => ops.listFacilities());

  const scope: Scope = { level, id: scopeId };

  const options: { value: Tab; label: string }[] = [
    { value: "OVERVIEW", label: t("dashboard:tabs.overview") },
    { value: "RISK_MAP", label: t("dashboard:tabs.riskMap") },
    { value: "EXPLORER", label: t("dashboard:tabs.explorer") },
  ];
  if (level === "NATIONAL") options.push({ value: "FEDERATION", label: t("dashboard:tabs.federation") });

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      <div className="flex flex-col gap-6 flex-1 min-w-0 w-full">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-title1">{summary?.scopeLabel ?? level}</h1>
          <div className="flex items-center gap-2">
            <SegmentedControl value={tab} onChange={setTab} options={options} />
            <Link
              href="/orders/new"
              aria-label={t("nav:composeNewAction")}
              className="w-9 h-9 flex items-center justify-center rounded-hig bg-tint-blue text-white hover:shadow-card-hover active:opacity-70 active:scale-90 transition-hig"
            >
              <Icon name="plus" className="w-4.5 h-4.5" />
            </Link>
          </div>
        </div>

        <div key={tab} className="flex flex-col gap-6 animate-fade-in-up">
          {tab === "OVERVIEW" && (
            <>
              {summaryError && (
                <ErrorBanner message={t("dashboard:scopeSummaryError")} onRetry={() => retrySummary()} />
              )}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <StatCard
                  icon="building"
                  label={t("dashboard:stats.facilitiesInScope")}
                  numericValue={summary?.facilityCount}
                  tone="brown"
                  loading={summaryLoading}
                  index={0}
                />
                <StatCard
                  icon="alert"
                  label={t("dashboard:stats.totalDeficit")}
                  numericValue={summary?.deficitTotal}
                  tone={summary && summary.deficitTotal > 0 ? "warning" : "default"}
                  loading={summaryLoading}
                  index={1}
                />
                <StatCard
                  icon="flag"
                  label={t("dashboard:stats.pendingRecommendations")}
                  numericValue={summary?.pendingRecommendations}
                  tone="pink"
                  href="/recommendations"
                  loading={summaryLoading}
                  index={2}
                />
              </div>

              {summary && (
                <ListGroup title={t("dashboard:alertsBySeverity")}>
                  {(
                    [
                      { severity: "CRITICAL", count: summary.alertCounts.critical, bar: "bg-tint-red" },
                      { severity: "HIGH", count: summary.alertCounts.high, bar: "bg-tint-orange" },
                      { severity: "WATCH", count: summary.alertCounts.watch, bar: "bg-tint-amber" },
                      { severity: "NORMAL", count: summary.alertCounts.normal, bar: "bg-label-quaternary" },
                    ] as { severity: Severity; count: number; bar: string }[]
                  ).map(({ severity, count, bar }) => {
                    const max = Math.max(
                      summary.alertCounts.critical,
                      summary.alertCounts.high,
                      summary.alertCounts.watch,
                      summary.alertCounts.normal,
                      1
                    );
                    return (
                      <div key={severity} className="flex flex-col gap-1.5 px-3.5 py-2">
                        <div className="flex items-center justify-between">
                          <SeverityBadge severity={severity} label={t(`common:severity.${severity}`)} muted={severity === "NORMAL"} />
                          <span className="text-callout text-label-secondary tabular-nums">{count}</span>
                        </div>
                        <ProportionBar value={count} max={max} className={bar} />
                      </div>
                    );
                  })}
                </ListGroup>
              )}
            </>
          )}

          {tab === "RISK_MAP" && markers && <RiskMap markers={markers} />}

          {tab === "EXPLORER" && products && facilities && (
            <ResourceExplorer products={products} facilities={facilities} />
          )}

          {tab === "FEDERATION" && <FederationPanel />}
        </div>
      </div>

      <AgentPane scope={scope} />
    </div>
  );
}
