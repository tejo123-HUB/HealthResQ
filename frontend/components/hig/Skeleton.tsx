/** Shimmer placeholder for a value that's still being fetched — used instead of a bare "—" so a
 * slow request reads as "in progress" rather than "empty" or "broken". */
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block rounded-md bg-bg-tertiary bg-[length:400px_100%] bg-no-repeat animate-shimmer ${className}`}
      style={{
        backgroundImage:
          "linear-gradient(90deg, var(--bg-tertiary) 0%, var(--fill-regular) 50%, var(--bg-tertiary) 100%)",
      }}
    />
  );
}
