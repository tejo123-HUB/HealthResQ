/** Placeholder for a value that's still being fetched — used instead of a bare "—" so a slow
 * request reads as "in progress" rather than "empty" or "broken". A soft gradient sweep (rather
 * than a flat opacity pulse) reads as "actively working" without being distracting — same
 * language most native OS placeholders use once loading takes long enough to notice. */
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block rounded-md bg-bg-tertiary bg-[length:200%_100%] bg-[linear-gradient(100deg,transparent_35%,var(--fill-thin)_50%,transparent_65%)] animate-shimmer ${className}`}
    />
  );
}
