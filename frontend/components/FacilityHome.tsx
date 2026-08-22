"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { useTranslation } from "react-i18next";
import { Card, StatCard } from "@/components/hig/Card";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Icon } from "@/components/hig/Icon";
import { SeverityBadge, riskSeverity, type Severity } from "@/components/hig/SeverityBadge";
import { InstructionList } from "@/components/InstructionList";
import { InboxPanel } from "@/components/mailbox/InboxPanel";
import { StockSparkline } from "@/components/StockSparkline";
import { ApiError } from "@/lib/api/client";
import { intelligence } from "@/lib/api/intelligence";
import { ops } from "@/lib/api/ops";
import type { InstructionStatus } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthContext";
import { useToast } from "@/lib/toast/ToastProvider";

type CardId = "lowStock" | "opd" | "beds" | "staff";
const ALL_CARD_IDS: CardId[] = ["lowStock", "opd", "beds", "staff"];
// Low-stock leads the grid — per Phase 8, it's the single most decision-relevant number on this
// screen (the thing most likely to require the facility to act today), so it should be seen
// before the merely-informational visit/bed/staff counts rather than trailing them.
const DEFAULT_ORDER: CardId[] = ["lowStock", "opd", "beds", "staff"];

type CardLayout = { order: CardId[]; hidden: CardId[] };
const CARD_LAYOUT_KEY = "healthresq.facilityHome.cardOrder";

function readStoredLayout(): CardLayout {
  if (typeof window === "undefined") return { order: DEFAULT_ORDER, hidden: [] };
  try {
    const raw = window.localStorage.getItem(CARD_LAYOUT_KEY);
    if (!raw) return { order: DEFAULT_ORDER, hidden: [] };
    const parsed = JSON.parse(raw) as Partial<CardLayout>;
    const storedOrder = (parsed.order ?? []).filter((id): id is CardId => ALL_CARD_IDS.includes(id as CardId));
    // Any card missing from a stale stored order (e.g. this list grows in a future release) is
    // appended at the end rather than silently dropped, so it still shows up somewhere.
    const order = [...storedOrder, ...ALL_CARD_IDS.filter((id) => !storedOrder.includes(id))];
    const hidden = (parsed.hidden ?? []).filter((id): id is CardId => ALL_CARD_IDS.includes(id as CardId));
    return { order, hidden };
  } catch {
    return { order: DEFAULT_ORDER, hidden: [] };
  }
}

const SEVERITY_RANK: Record<Severity, number> = {
  CRITICAL: 4,
  HIGH: 3,
  WATCH: 2,
  NORMAL: 1,
  NEUTRAL: 0,
  SUCCESS: 0,
};

/** OPS-06: today's footfall/beds/staff/low-stock summary plus the instruction inbox, sourced
 * exclusively from this facility's own mailbox (via InboxPanel) and its own instructions
 * (InstructionList) — never another facility's. The "Overview" tab of the facility's single
 * workspace page. */
export function FacilityHome() {
  const { t } = useTranslation(["hms", "common"]);
  const { facility } = useAuth();
  const facilityId = facility!.id;
  const toast = useToast();

  const { data: footfall, isLoading: footfallLoading, error: footfallError } = useSWR(["footfall", facilityId], () =>
    ops.getFootfall(facilityId)
  );
  // A 404 here means "no capacity submitted yet", a legitimate empty state (OPS-06 read path) —
  // not a fetch failure, so it's swallowed rather than surfaced as an error.
  const { data: capacity, isLoading: capacityLoading } = useSWR(["capacity", facilityId], () =>
    ops.getCapacity(facilityId).catch(() => null)
  );
  const { data: inventory, isLoading: inventoryLoading, error: inventoryError } = useSWR(
    ["inventory", facilityId],
    () => ops.getInventory(facilityId)
  );
  const {
    data: instructions,
    isLoading: instructionsLoading,
    error: instructionsError,
    mutate: mutateInstructions,
  } = useSWR(["instructions", facilityId], () => ops.getInstructions(facilityId));
  // Risk markers and the product catalog are supplementary context for the low-stock card (real
  // per-product severity instead of the old flat threshold) rather than core OPS-06 stats, so a
  // failure here is swallowed the same way `capacity` is above — the card just falls back to
  // no-signal/NORMAL rather than blocking or erroring the whole page.
  const { data: riskMarkers } = useSWR(["riskMarkers", facilityId], () =>
    intelligence.getRiskMarkers().catch(() => [])
  );
  const { data: products } = useSWR(["products"], () => ops.listProducts().catch(() => []));

  const [layout, setLayout] = useState<CardLayout>({ order: DEFAULT_ORDER, hidden: [] });
  const [customizing, setCustomizing] = useState(false);

  useEffect(() => {
    setLayout(readStoredLayout());
  }, []);

  const persistLayout = (next: CardLayout) => {
    setLayout(next);
    try {
      window.localStorage.setItem(CARD_LAYOUT_KEY, JSON.stringify(next));
    } catch {
      // localStorage can throw in private-browsing/quota-exceeded contexts — customize state is
      // a convenience, not something worth surfacing an error for.
    }
  };

  const moveCard = (id: CardId, direction: -1 | 1) => {
    const idx = layout.order.indexOf(id);
    const swapWith = idx + direction;
    if (swapWith < 0 || swapWith >= layout.order.length) return;
    const nextOrder = [...layout.order];
    const temp = nextOrder[idx];
    nextOrder[idx] = nextOrder[swapWith]!;
    nextOrder[swapWith] = temp!;
    persistLayout({ ...layout, order: nextOrder });
  };

  const toggleHidden = (id: CardId) => {
    const hidden = layout.hidden.includes(id)
      ? layout.hidden.filter((h) => h !== id)
      : [...layout.hidden, id];
    persistLayout({ ...layout, hidden });
  };

  const opdVisits = (footfall ?? []).reduce((sum, f) => sum + f.opdVisits, 0);

  // Per-product severity, keyed by productId — replaces the old hardcoded `currentStock < 100`
  // check. Alerts only exist for facility+product pairs that have had a forecast computed, so a
  // product with no matching alert is treated as no-signal/NORMAL rather than flagged.
  const facilityMarker = (riskMarkers ?? []).find((m) => m.facilityId === facilityId);
  const alertsByProduct = new Map<string, { severity: Severity; daysToStockout: number | null }>();
  for (const alert of facilityMarker?.alerts ?? []) {
    if (alert.facilityId !== facilityId) continue;
    alertsByProduct.set(alert.productId, {
      severity: riskSeverity(alert.severity),
      daysToStockout: alert.daysToStockout,
    });
  }

  const productName = (productId: string) => products?.find((p) => p.id === productId)?.name ?? productId;

  const lowStockCount = (inventory ?? []).filter((line) => {
    const alert = alertsByProduct.get(line.productId);
    return alert && (alert.severity === "WATCH" || alert.severity === "HIGH" || alert.severity === "CRITICAL");
  }).length;

  // The 1–2 most decision-relevant products for the sparkline panel below: worst severity first,
  // then soonest days-to-stockout. Products with no alert (no-signal) sort last, so a facility
  // with nothing at risk still shows its two catalog items rather than an empty panel.
  const topRiskProducts = [...(inventory ?? [])]
    .map((line) => {
      const alert = alertsByProduct.get(line.productId);
      return {
        productId: line.productId,
        severity: (alert?.severity ?? "NORMAL") as Severity,
        daysToStockout: alert?.daysToStockout ?? null,
      };
    })
    .sort((a, b) => {
      const rankDiff = SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity];
      if (rankDiff !== 0) return rankDiff;
      const aDays = a.daysToStockout ?? Infinity;
      const bDays = b.daysToStockout ?? Infinity;
      return aDays - bDays;
    })
    .slice(0, 2);

  const statsFailed = footfallError || inventoryError;

  const CARD_DEFS: Record<
    CardId,
    { icon: Parameters<typeof Icon>[0]["name"]; label: string; render: () => { numericValue?: number; value?: string; tone: Parameters<typeof StatCard>[0]["tone"]; loading: boolean } }
  > = {
    lowStock: {
      icon: "alert",
      label: t("hms:cards.lowStock"),
      render: () => ({
        numericValue: lowStockCount,
        tone: lowStockCount > 0 ? "warning" : "default",
        loading: inventoryLoading,
      }),
    },
    opd: {
      icon: "chart",
      label: t("hms:cards.opd"),
      render: () => ({ numericValue: opdVisits, tone: "pink", loading: footfallLoading }),
    },
    beds: {
      icon: "bed",
      label: t("hms:cards.beds"),
      render: () => ({
        value: capacity ? `${capacity.beds.occupied}/${capacity.beds.total}` : "—",
        tone: "yellow",
        loading: capacityLoading,
      }),
    },
    staff: {
      icon: "checkCircle",
      label: t("hms:cards.staff"),
      render: () => ({
        numericValue: capacity ? capacity.staff.reduce((s, r) => s + r.present, 0) : undefined,
        value: capacity ? undefined : "—",
        tone: "brown",
        loading: capacityLoading,
      }),
    },
  };

  const visibleOrder = customizing ? layout.order : layout.order.filter((id) => !layout.hidden.includes(id));

  return (
    <div className="flex flex-col gap-6">
      {statsFailed && <ErrorBanner message={t("hms:couldntLoadTodaySummary")} />}

      <div className="flex items-center justify-between">
        <p className="text-footnote text-label-secondary uppercase">{t("hms:today")}</p>
        <button
          type="button"
          onClick={() => setCustomizing((c) => !c)}
          className="text-footnote font-semibold text-tint-blue hover:opacity-70 transition-hig"
        >
          {customizing ? t("hms:done") : t("hms:customize")}
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {visibleOrder.map((id, index) => {
          const def = CARD_DEFS[id];
          const props = def.render();
          const isHidden = layout.hidden.includes(id);
          return (
            <div key={id} className={`relative ${customizing && isHidden ? "opacity-40" : ""}`}>
              <StatCard icon={def.icon} label={def.label} tone={props.tone} loading={props.loading} value={props.value} numericValue={props.numericValue} index={index} />
              {customizing && (
                <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-1 px-2 py-1.5 bg-bg/95 border-t border-separator rounded-b-hig">
                  <button
                    type="button"
                    aria-label={t("hms:moveLeft", { label: def.label })}
                    onClick={() => moveCard(id, -1)}
                    disabled={layout.order.indexOf(id) === 0}
                    className="p-1 rounded-full hover:bg-fill-thin disabled:opacity-30 transition-hig"
                  >
                    <Icon name="chevronLeft" className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleHidden(id)}
                    className={`flex items-center gap-1 text-caption2 font-semibold px-1.5 py-0.5 rounded-full transition-hig ${
                      isHidden ? "text-label-tertiary" : "text-tint-blue"
                    }`}
                  >
                    <Icon name={isHidden ? "eyeOff" : "eye"} className="w-3 h-3" />
                    {isHidden ? t("hms:hidden") : t("hms:pinned")}
                  </button>
                  <button
                    type="button"
                    aria-label={t("hms:moveRight", { label: def.label })}
                    onClick={() => moveCard(id, 1)}
                    disabled={layout.order.indexOf(id) === layout.order.length - 1}
                    className="p-1 rounded-full hover:bg-fill-thin disabled:opacity-30 transition-hig"
                  >
                    <Icon name="chevronRight" className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {topRiskProducts.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {topRiskProducts.map((p) => (
            <Card key={p.productId}>
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-callout font-semibold truncate">{productName(p.productId)}</p>
                <SeverityBadge
                  severity={p.severity}
                  label={
                    p.severity === "NORMAL"
                      ? t("hms:noSignal")
                      : p.daysToStockout !== null
                        ? t("hms:daysToStockout", { days: p.daysToStockout })
                        : t(`common:severity.${p.severity}`)
                  }
                  muted
                />
              </div>
              <p className="text-caption2 text-label-tertiary mb-1">{t("hms:projectedStock")}</p>
              <StockSparkline facilityId={facilityId} productId={p.productId} />
            </Card>
          ))}
        </div>
      )}

      <InboxPanel unitId={facilityId} />

      {instructionsError ? (
        <ErrorBanner message={t("hms:couldntLoadInstructions")} />
      ) : (
        <InstructionList
          instructions={instructions ?? []}
          loading={instructionsLoading}
          onAdvance={async (instruction, next: InstructionStatus) => {
            try {
              await ops.updateInstructionStatus(instruction.id, next);
              mutateInstructions();
              toast.success(
                next === "BLOCKED"
                  ? t("hms:instructionReportedBlocked")
                  : t("hms:instructionMarked", { status: t(`common:status.${next}`) })
              );
            } catch (err) {
              toast.error(err instanceof ApiError ? err.message : t("hms:couldntUpdateInstruction"));
            }
          }}
        />
      )}
    </div>
  );
}
