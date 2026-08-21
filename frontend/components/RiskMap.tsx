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
      const el = document.createElement("button");
      el.style.width = "16px";
      el.style.height = "16px";
      el.style.borderRadius = "50%";
      el.style.border = "2px solid white";
      el.style.background = SEVERITY_COLOR[m.worstSeverity];
      el.style.cursor = "pointer";
      el.title = `${m.facilityName} — ${m.worstSeverity}`;
      el.onclick = () => onSelect?.(m);
      return new maplibregl.Marker({ element: el }).setLngLat([m.location.lng, m.location.lat]).addTo(map);
    });

    return () => markerInstances.forEach((mk) => mk.remove());
  }, [located, onSelect]);

  return <div ref={containerRef} className="w-full h-80 rounded-hig overflow-hidden border border-separator" />;
}
