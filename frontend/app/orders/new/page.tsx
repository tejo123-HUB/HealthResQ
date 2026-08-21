"use client";

import { useState, type FormEvent } from "react";
import useSWR from "swr";
import { AuthGuard } from "@/components/AuthGuard";
import { BackButton } from "@/components/hig/BackButton";
import { Button } from "@/components/hig/Button";
import { Card } from "@/components/hig/Card";
import { ops } from "@/lib/api/ops";
import { command } from "@/lib/api/command";
import { useAuth } from "@/lib/auth/AuthContext";

/** CMD-07: an authority composes a recommendation directly, restricted to facilities/units in
 * their own scope (real facility list, via GET /facilities — legitimately scoped for a
 * DISTRICT/STATE/NATIONAL caller under OPS-02). The submission itself is a stub — CMD-01's real
 * lifecycle and INT feasibility validation don't exist until Direction 2/3 ship. */
function ActionComposer() {
  const { scope } = useAuth();
  const { data: facilities } = useSWR(["facilities", scope?.level, scope?.id], () => ops.listFacilities());
  const { data: products } = useSWR(["products"], () => ops.listProducts());

  const [destinationFacilityId, setDestinationFacilityId] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState(100);
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await command.composeAction({ destinationFacilityId, productId, quantity, reason });
      setSubmitted(true);
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
              className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator"
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
              className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator"
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
              className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-footnote text-label-secondary">Reason</span>
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator"
              rows={3}
            />
          </label>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Submitting…" : "Submit for review"}
          </Button>
          {submitted && (
            <p className="text-footnote text-tint-green">
              Recorded (stub — no real CMD-01 recommendation exists until Direction 2/3 ship).
            </p>
          )}
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
