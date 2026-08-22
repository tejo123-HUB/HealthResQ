"use client";

import useSWR from "swr";
import { AuthGuard } from "@/components/AuthGuard";
import { ListGroup, ListRow } from "@/components/hig/Card";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Icon } from "@/components/hig/Icon";
import { Skeleton } from "@/components/hig/Skeleton";
import { InstructionList } from "@/components/InstructionList";
import { InboxPanel } from "@/components/mailbox/InboxPanel";
import { ApiError } from "@/lib/api/client";
import { ops } from "@/lib/api/ops";
import type { InstructionStatus } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthContext";
import { useToast } from "@/lib/toast/ToastProvider";

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

  const productName = (id: string) => products?.find((p) => p.id === id)?.name ?? id;

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

      <InstructionList
        title="Dispatch orders (ACKNOWLEDGE → PREPARE → DISPATCH)"
        instructions={warehouse?.orders ?? []}
        loading={isLoading}
        onAdvance={async (order, next: InstructionStatus) => {
          try {
            await ops.updateWarehouseOrderStatus(facilityId, order.id, next);
            mutate();
            toast.success(next === "BLOCKED" ? "Order reported as blocked" : `Order marked ${next}`);
          } catch (err) {
            toast.error(err instanceof ApiError ? err.message : "Couldn't update order — try again.");
          }
        }}
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
