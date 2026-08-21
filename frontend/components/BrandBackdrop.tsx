import type { ReactNode } from "react";

/** Slow-drifting, blurred brand-color blobs behind `children` — decorative only (see
 * lib/theme/tokens.css's --brand-* tokens), used for brand moments like the login page. Never
 * used where a color needs to mean something (that's the --tint-* system). Wash tokens already
 * carry light/dark variants, so this needs no theme branching of its own. */
export function BrandBackdrop({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <span className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-brand-teal-wash blur-3xl animate-blob-drift-a" />
        <span className="absolute top-1/3 -right-32 w-[28rem] h-[28rem] rounded-full bg-brand-orange-wash blur-3xl animate-blob-drift-b" />
        <span className="absolute -bottom-32 left-1/4 w-96 h-96 rounded-full bg-brand-gold-wash blur-3xl animate-blob-drift-c" />
      </div>
      {children}
    </div>
  );
}
