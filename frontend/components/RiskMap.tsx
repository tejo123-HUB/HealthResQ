"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { RiskMarker, Severity } from "@/lib/api/types";

const SEVERITY_COLOR: Record<Severity, string> = {
  NORMAL: "#8e8e93",
  WATCH: "#ff9500",
  HIGH: "#ff9500",
  CRITICAL: "#ff3b30",
};

// No-API-key OSM raster style — consistent with the architecture doc's "no registration-gated
// external dependency" policy (Section 12); this is a dev/prototype shell, not a production tile
// provider commitment.
const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export function RiskMap({ markers, onSelect }: { markers: RiskMarker[]; onSelect?: (m: RiskMarker) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  // A facility with no recorded coordinates (OPS-01's location is nullable) has nowhere to plot —
  // skipped here rather than guessing a fallback position.
  const located = markers.filter((m): m is RiskMarker & { location: NonNullable<RiskMarker["location"]> } => m.location !== null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: located[0] ? [located[0].location.lng, located[0].location.lat] : [80.63, 16.5],
      zoom: 10,
    });
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const markerInstances = located.map((m) => {
      const wrap = document.createElement("button");
      wrap.style.position = "relative";
      wrap.style.width = "16px";
      wrap.style.height = "16px";
      wrap.style.cursor = "pointer";
      wrap.style.transition = "transform 150ms ease-out";
      wrap.title = `${m.facilityName} — ${m.worstSeverity}`;
      wrap.onmouseenter = () => (wrap.style.transform = "scale(1.35)");
      wrap.onmouseleave = () => (wrap.style.transform = "scale(1)");
      wrap.onclick = () => onSelect?.(m);

      // A CRITICAL facility gets a pulsing ring so it's found on the map before anything else —
      // same visual language as SeverityBadge's glow-pulse and LoadingScreen's pulse-ring.
      if (m.worstSeverity === "CRITICAL") {
        const ring = document.createElement("span");
        ring.className = "animate-pulse-ring";
        ring.style.position = "absolute";
        ring.style.inset = "0";
        ring.style.borderRadius = "50%";
        ring.style.background = SEVERITY_COLOR.CRITICAL;
        wrap.appendChild(ring);
      }

      const dot = document.createElement("span");
      dot.style.position = "absolute";
      dot.style.inset = "0";
      dot.style.borderRadius = "50%";
      dot.style.border = "2px solid white";
      dot.style.background = SEVERITY_COLOR[m.worstSeverity];
      dot.style.boxShadow = "0 1px 3px rgba(0,0,0,0.35)";
      wrap.appendChild(dot);

      return new maplibregl.Marker({ element: wrap }).setLngLat([m.location.lng, m.location.lat]).addTo(map);
    });

    return () => markerInstances.forEach((mk) => mk.remove());
  }, [located, onSelect]);

  return <div ref={containerRef} className="w-full h-80 rounded-hig overflow-hidden border border-separator shadow-card animate-fade-in-up" />;
}
