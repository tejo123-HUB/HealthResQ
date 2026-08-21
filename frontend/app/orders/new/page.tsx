"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import useSWR from "swr";
import { AuthGuard } from "@/components/AuthGuard";
import { BackButton } from "@/components/hig/BackButton";
import { Button } from "@/components/hig/Button";
import { Card } from "@/components/hig/Card";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { ApiError } from "@/lib/api/client";
import { ops } from "@/lib/api/ops";
import { command } from "@/lib/api/command";
import { useAuth } from "@/lib/auth/AuthContext";

/** CMD-07: an authority composes a recommendation directly, restricted to facilities/units in
 * their own scope (real facility list, via GET /facilities — legitimately scoped for a
 * DISTRICT/STATE/NATIONAL caller under OPS-02). Runs the same INT feasibility validation and
 * CMD-01 lifecycle as an agent-drafted recommendation (origin=HUMAN) before it can be approved. */
function ActionComposer() {
  const router = useRouter();
  const { scope } = useAuth();
  const { data: facilities } = useSWR(["facilities", scope?.level, scope?.id], () => ops.listFacilities());
  const { data: products } = useSWR(["products"], () => ops.listProducts());

  const [destinationFacilityId, setDestinationFacilityId] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState(100);
  const [reason, setReason] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const recommendation = await command.composeAction({ destinationFacilityId, productId, quantity, reason });
      router.push(`/recommendations/${recommendation.id}`);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "That submission couldn't be completed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-lg">
      <BackButton />
      <h1 className="text-title1 mb-1">Compose action</h1>
      <p className="text-body text-label-secondary mb-6">
        Restricted to facilities within your own scope ({scope?.level}).
      </p>
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-footnote text-label-secondary">Destination facility</span>
            <select
              required
              value={destinationFacilityId}
              onChange={(e) => setDestinationFacilityId(e.target.value)}
              className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
            >
              <option value="" disabled>
                Select a facility
              </option>
              {facilities?.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} ({f.type})
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-footnote text-label-secondary">Resource</span>
            <select
              required
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
            >
              <option value="" disabled>
                Select a resource
              </option>
              {products?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-footnote text-label-secondary">Quantity</span>
            <input
              type="number"
              min={1}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-footnote text-label-secondary">Reason</span>
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
              rows={3}
            />
          </label>
          <Button type="submit" disabled={submitting} className="flex items-center justify-center gap-2">
            {submitting ? (
              <>
                <span className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot" />
                  <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot [animation-delay:0.15s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-bounce-dot [animation-delay:0.3s]" />
                </span>
                Submitting…
              </>
            ) : (
              "Submit for review"
            )}
          </Button>
          {submitError && <ErrorBanner message={submitError} />}
        </form>
      </Card>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <ActionComposer />
    </AuthGuard>
  );
}
