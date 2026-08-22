"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import useSWR from "swr";
import { AuthGuard } from "@/components/AuthGuard";
import { ListGroup, ListRow } from "@/components/hig/Card";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Icon } from "@/components/hig/Icon";
import { Skeleton } from "@/components/hig/Skeleton";
import { InstructionList } from "@/components/InstructionList";
import { OrderStageDetail } from "@/components/warehouse/OrderStageDetail";
import { InboxPanel } from "@/components/mailbox/InboxPanel";
import { ApiError } from "@/lib/api/client";
import { ops } from "@/lib/api/ops";
import type { Instruction, InstructionStatus, Warehouse } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthContext";
import { useToast } from "@/lib/toast/ToastProvider";
import { enqueueAdvance, getPendingCount, retryQueuedAdvances, subscribeToQueue } from "@/lib/offline/orderAdvanceQueue";

function WarehouseScreen() {
  const { facility } = useAuth();
  const facilityId = facility!.id;
  const toast = useToast();
  const {
    data: warehouse,
    isLoading,
    error,
    mutate,
  } = useSWR(["warehouse", facilityId], () => ops.getWarehouse(facilityId));
  const { data: products } = useSWR(["products"], () => ops.listProducts());
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  // Warehouse-advance-only offline support (see lib/offline/orderAdvanceQueue.ts) — pending count
  // for the sync-badge pill, kept live across tabs/queue mutations via useSyncExternalStore rather
  // than ad-hoc state + effects.
  const pendingCount = useSyncExternalStore(subscribeToQueue, getPendingCount, () => 0);

  // Drain the offline queue as soon as connectivity returns, then refresh the warehouse view so
  // any orders that advanced while offline reflect the server's real state.
  useEffect(() => {
    const handleOnline = () => {
      retryQueuedAdvances().then(() => mutate());
    };
    window.addEventListener("online", handleOnline);
    return () => window.removeEventListener("online", handleOnline);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facilityId]);

  const productName = (id: string | null) => (id ? products?.find((p) => p.id === id)?.name ?? id : "—");

  const selectedOrder = warehouse?.orders.find((o) => o.id === selectedOrderId) ?? null;

  async function handleAdvance(order: Instruction, next: InstructionStatus) {
    const optimisticWarehouse: Warehouse | undefined = warehouse
      ? { ...warehouse, orders: warehouse.orders.map((o) => (o.id === order.id ? { ...o, status: next } : o)) }
      : undefined;

    try {
      await mutate(() => ops.updateWarehouseOrderStatus(facilityId, order.id, next), {
        optimisticData: optimisticWarehouse,
        // Only roll the optimistic UI back for a genuine server rejection (bad transition, auth,
        // etc). A network failure (offline) leaves the optimistic state showing — it's queued
        // below and will reconcile with the server once the retry succeeds.
        rollbackOnError: (err) => err instanceof ApiError,
        revalidate: false,
      });
      toast.success(next === "BLOCKED" ? "Order reported as blocked" : `Order marked ${next}`);
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.message);
      } else {
        // Not a server rejection — most likely offline. Queue the advance for automatic retry
        // rather than losing it; the optimistic UI above already reflects the intended state.
        enqueueAdvance(facilityId, order.id, next);
        toast.error("You're offline — this will sync automatically once you're back online.");
      }
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-title1">{facility!.name}</h1>

      {error ? (
        <ErrorBanner message="Couldn't load warehouse data." onRetry={() => mutate()} />
      ) : (
        <ListGroup title="Stock on hand">
          {isLoading &&
            [0, 1, 2].map((i) => (
              <div key={i} className="px-4 py-3 flex items-center justify-between gap-3">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-10" />
              </div>
            ))}
          {(warehouse?.inventory ?? []).map((line, i) => (
            <ListRow
              key={line.productId}
              label={
                <span
                  style={{ animationDelay: `${i * 40}ms` }}
                  className="flex items-center gap-2.5 animate-fade-in-up"
                >
                  <Icon name="box" className="w-4.5 h-4.5 text-label-secondary" />
                  {productName(line.productId)}
                </span>
              }
              value={line.currentStock}
            />
          ))}
        </ListGroup>
      )}

      <InboxPanel unitId={facilityId} />

      {pendingCount > 0 && (
        <div className="flex items-center justify-end gap-3 -mb-3">
          <span className="flex items-center gap-1.5 text-caption1 font-semibold text-occ-filled bg-occ-filled-wash rounded-full pl-1.5 pr-2.5 py-1">
            <Icon name="refresh" className="w-3.5 h-3.5" />
            {pendingCount} order{pendingCount === 1 ? "" : "s"} syncing
          </span>
        </div>
      )}

      {/* At-a-glance simplified tracker — unchanged 3-stage view (see components/InstructionList.tsx). */}
      <InstructionList
        title="Dispatch orders (ACKNOWLEDGE → PREPARE → DISPATCH)"
        instructions={warehouse?.orders ?? []}
        loading={isLoading}
        onAdvance={handleAdvance}
      />

      {/* Tap-to-open detail view of the real 6-status machine — new for this phase, since
          InstructionList's rows aren't individually tappable. */}
      {!isLoading && (warehouse?.orders?.length ?? 0) > 0 && (
        <ListGroup title="Order details (tap for full status)">
          {(warehouse?.orders ?? []).map((order, i) => (
            <ListRow
              key={order.id}
              onClick={() => setSelectedOrderId(order.id)}
              label={
                <span
                  style={{ animationDelay: `${i * 40}ms` }}
                  className="flex items-center gap-2.5 animate-fade-in-up truncate"
                >
                  <Icon name="box" className="w-4.5 h-4.5 text-label-secondary shrink-0" />
                  <span className="truncate">{order.action}</span>
                </span>
              }
              value={
                <span className="flex items-center gap-1.5">
                  {order.status}
                  <Icon name="chevronRight" className="w-3.5 h-3.5" />
                </span>
              }
            />
          ))}
        </ListGroup>
      )}

      <OrderStageDetail
        order={selectedOrder}
        open={selectedOrderId !== null}
        productName={productName(selectedOrder?.productId ?? null)}
        onAdvance={handleAdvance}
        onClose={() => setSelectedOrderId(null)}
      />
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <WarehouseScreen />
    </AuthGuard>
  );
}
