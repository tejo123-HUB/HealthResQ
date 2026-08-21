"use client";

import useSWR from "swr";
import { AuthGuard } from "@/components/AuthGuard";
import { BackButton } from "@/components/hig/BackButton";
import { ListGroup, ListRow } from "@/components/hig/Card";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { recommendationSeverity, SeverityBadge } from "@/components/hig/SeverityBadge";
import { Skeleton } from "@/components/hig/Skeleton";
import { useRouter } from "next/navigation";
import { command } from "@/lib/api/command";

/** CMD-09's recommendation queue for the caller's own scope — the destination for the dashboard's
 * "Pending recommendations" stat and the AI-suggestion pane's "Review full recommendation" link,
 * neither of which can point at one hard-coded id now that recommendations are real, scope-varying
 * database rows instead of a single fixture. */
function RecommendationsList() {
  const router = useRouter();
  const {
    data: recommendations,
    isLoading,
    error,
    mutate,
  } = useSWR(["recommendations"], () => command.listRecommendations("DRAFT,PENDING_REVIEW,OUTDATED"));

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <BackButton />
      <h1 className="text-title1">Recommendations</h1>

      {error && <ErrorBanner message="Couldn't load recommendations." onRetry={() => mutate()} />}

      {isLoading && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      )}

      {recommendations && recommendations.length === 0 && (
        <p className="text-body text-label-secondary">No pending recommendations in your scope right now.</p>
      )}

      {recommendations && recommendations.length > 0 && (
        <ListGroup>
          {recommendations.map((r) => (
            <ListRow
              key={r.id}
              onClick={() => router.push(`/recommendations/${r.id}`)}
              label={
                <span className="flex flex-col gap-0.5">
                  <span className="flex items-center gap-2">
                    {r.problem}
                    {r.origin === "HUMAN" && <span className="text-caption1 text-label-tertiary">· human</span>}
                  </span>
                </span>
              }
              value={<SeverityBadge severity={recommendationSeverity(r.status)} label={r.status.replace("_", " ")} />}
            />
          ))}
        </ListGroup>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <RecommendationsList />
    </AuthGuard>
  );
}
