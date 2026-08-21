/** Placeholder for a value that's still being fetched — used instead of a bare "—" so a slow
 * request reads as "in progress" rather than "empty" or "broken". A soft opacity pulse on a flat
 * fill, matching iOS's own native placeholder shimmer, rather than a moving gradient sweep. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <span className={`inline-block rounded-md bg-bg-tertiary animate-skeleton-pulse ${className}`} />;
}
