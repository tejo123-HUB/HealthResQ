"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { RiskMarker } from "@/lib/fixtures/riskMap";

const SEVERITY_COLOR: Record<RiskMarker["severity"], string> = {
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

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: markers[0] ? [markers[0].lng, markers[0].lat] : [80.63, 16.5],
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

    const markerInstances = markers.map((m) => {
      const el = document.createElement("button");
      el.style.width = "16px";
      el.style.height = "16px";
      el.style.borderRadius = "50%";
      el.style.border = "2px solid white";
      el.style.background = SEVERITY_COLOR[m.severity];
      el.style.cursor = "pointer";
      el.title = `${m.name} — ${m.severity}`;
      el.onclick = () => onSelect?.(m);
      return new maplibregl.Marker({ element: el }).setLngLat([m.lng, m.lat]).addTo(map);
    });

    return () => markerInstances.forEach((mk) => mk.remove());
  }, [markers, onSelect]);

  return <div ref={containerRef} className="w-full h-80 rounded-hig overflow-hidden border border-separator" />;
}
