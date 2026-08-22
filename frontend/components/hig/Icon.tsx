// Small SF-Symbols-style stroke icon set — inline SVG, no icon-library dependency (keeps the
// self-hosted/offline-friendly footprint the architecture doc asks for). Icons are paired with a
// label everywhere they appear (never color/icon alone) so meaning doesn't depend on reading.

import type { SVGProps } from "react";

const PATHS: Record<string, string> = {
  home: "M3 11.5 12 4l9 7.5M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9",
  bed: "M3 18v-7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v7M3 18v2M21 18v2M3 13h18M7 9V6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v3",
  building: "M4 21V5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v16M12 21V9a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v12M4 21h16M7 7h1M7 11h1M7 15h1M15 12h1M15 16h1",
  box: "M3 8l9-5 9 5-9 5-9-5Zm0 0v9l9 5m0-14v14m9-14v9l-9 5",
  inbox: "M4 12h4l2 3h4l2-3h4M4 12l1.6-6.4A1 1 0 0 1 6.56 5h10.88a1 1 0 0 1 .96.6L20 12M4 12v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6",
  check: "M5 13l4 4L19 7",
  checkCircle: "M9 12l2 2 4-4M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  alert: "M12 9v4m0 4h.01M10.3 3.9 2.6 17a1 1 0 0 0 .87 1.5h17a1 1 0 0 0 .87-1.5L13.7 3.9a1 1 0 0 0-1.74 0Z",
  chevronRight: "m9 6 6 6-6 6",
  chevronLeft: "m15 6-6 6 6 6",
  plus: "M12 5v14M5 12h14",
  refresh: "M4 4v5h5M20 20v-5h-5M4.6 9a8 8 0 0 1 14.4-3M19.4 15a8 8 0 0 1-14.4 3",
  signOut: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  map: "M9 20 3 17V4l6 3m0 13 6-3m-6 3V7m6 10 6 3V7l-6-3m0 13V4m0 3-6-3",
  chart: "M4 20V10m6 10V4m6 16v-7",
  flag: "M5 21V4m0 3h13l-3 4 3 4H5",
  lock: "M6 11V8a6 6 0 1 1 12 0v3M5 11h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1Z",
  sun: "M12 3v2m0 14v2M4.2 4.2l1.4 1.4m12.8 12.8 1.4 1.4M3 12h2m14 0h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  moon: "M20 14.5a8 8 0 1 1-9.5-9.5 6.5 6.5 0 0 0 9.5 9.5Z",
  x: "M18 6 6 18M6 6l12 12",
  pulse: "M22 12h-4l-3 9L9 3l-3 9H2",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35",
  chevronDown: "m6 9 6 6 6-6",
};

export function Icon({
  name,
  className = "w-5 h-5",
  ...props
}: { name: keyof typeof PATHS } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...props}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
