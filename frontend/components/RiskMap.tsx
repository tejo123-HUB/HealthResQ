"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { createRoot, type Root } from "react-dom/client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "@/components/hig/Icon";
import { MotionPauseControl } from "@/components/hig/MotionPauseControl";
import { useReducedMotion } from "@/lib/hooks/useReducedMotion";
import { intelligence } from "@/lib/api/intelligence";
import type { HexCell, RiskMarker, Severity } from "@/lib/api/types";

// Fallback values match the *light*-theme tokens in lib/theme/tokens.css — used only before the
// real CSS custom properties can be read (SSR / first paint) or if a token is ever missing, never
// as the primary source of truth.
const FALLBACK_SEVERITY_COLOR: Record<Severity, string> = {
  NORMAL: "#8e8e93",
  WATCH: "#d19100",
  HIGH: "#ff9500",
  CRITICAL: "#ff3b30",
};

/** Reads severity colors from lib/theme/tokens.css's custom properties instead of a second
 * hardcoded hex map, so this can't silently drift from SeverityBadge again (WATCH/HIGH used to
 * share the identical #ff9500). NORMAL is sourced from --occ-filled (the app's neutral "no
 * alert"/non-alarm gray) rather than a --label-* token, since the label tokens are translucent
 * (rgba over the page background) and unsuitable as an opaque marker fill on top of map tiles. */
function readSeverityColors(): Record<Severity, string> {
  if (typeof window === "undefined") return FALLBACK_SEVERITY_COLOR;
  const styles = getComputedStyle(document.documentElement);
  const pick = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback;
  return {
    NORMAL: pick("--occ-filled", FALLBACK_SEVERITY_COLOR.NORMAL),
    WATCH: pick("--tint-amber", FALLBACK_SEVERITY_COLOR.WATCH),
    HIGH: pick("--tint-orange", FALLBACK_SEVERITY_COLOR.HIGH),
    CRITICAL: pick("--tint-red", FALLBACK_SEVERITY_COLOR.CRITICAL),
  };
}

// Redundant shape per tier (never color-alone): each severity gets both a distinct pin silhouette
// and the same icon SeverityBadge already uses for that tier (check for Normal, alert for the
// rest), so severity reads at a glance on a small pin without depending on hue discrimination.
function ShapeMark({ severity, fill }: { severity: Severity; fill: string }) {
  switch (severity) {
    case "NORMAL":
      return <circle cx="10" cy="10" r="8" fill={fill} stroke="white" strokeWidth="2" />;
    case "WATCH":
      return (
        <rect x="4" y="4" width="12" height="12" fill={fill} stroke="white" strokeWidth="2" transform="rotate(45 10 10)" />
      );
    case "HIGH":
      return <polygon points="10,2 18,17 2,17" fill={fill} stroke="white" strokeWidth="2" strokeLinejoin="round" />;
    case "CRITICAL":
      return <rect x="2" y="2" width="16" height="16" rx="3" fill={fill} stroke="white" strokeWidth="2" />;
  }
}

function MarkerGlyph({ severity, color, pulsing }: { severity: Severity; color: string; pulsing: boolean }) {
  const iconName = severity === "NORMAL" ? "check" : "alert";
  return (
    <div className="relative" style={{ width: 20, height: 20 }}>
      {pulsing && (
        <span className="absolute inset-0 rounded-full animate-pulse-ring" style={{ background: color }} aria-hidden="true" />
      )}
      <svg viewBox="0 0 20 20" width={20} height={20} className="relative block drop-shadow-[0_1px_3px_rgba(0,0,0,0.35)]">
        <ShapeMark severity={severity} fill={color} />
      </svg>
      <Icon name={iconName} className="absolute inset-0 m-auto w-2.5 h-2.5 text-white pointer-events-none" />
    </div>
  );
}

type LocatedMarker = RiskMarker & { location: NonNullable<RiskMarker["location"]> };

// Free, no-API-key vector basemap. OpenFreeMap's hosted "Liberty" style needs no registration/key
// and no self-hosted tile bundle (unlike Protomaps' usual self-hosted-PMTiles path) — the closest
// vector equivalent to the previous raw-OSM-raster policy (architecture doc §12: no
// registration-gated external dependency). Raw OSM raster tiles remain as a last-resort fallback
// if the vector style ever fails to load.
const VECTOR_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

const OSM_FALLBACK_STYLE: maplibregl.StyleSpecification = {
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

function minDaysToStockout(m: RiskMarker): number {
  const days = m.alerts.map((a) => a.daysToStockout).filter((d): d is number => d !== null);
  return days.length ? Math.min(...days) : Number.POSITIVE_INFINITY;
}

/** Rarity budget: only the single most-urgent CRITICAL facility currently in the viewport pulses
 * — not every CRITICAL marker. Recomputed on pan/zoom so "the one outlier" always tracks whatever
 * is actually visible, instead of a fixed unconditional pulse on every CRITICAL pin. */
function computePulseTarget(map: maplibregl.Map, located: LocatedMarker[]): string | null {
  const bounds = map.getBounds();
  const visible = located.filter((m) => bounds.contains([m.location.lng, m.location.lat]));
  const critical = visible.filter((m) => m.worstSeverity === "CRITICAL");
  if (critical.length === 0) return null;

  let worst: LocatedMarker | undefined;
  for (const m of critical) {
    if (!worst) {
      worst = m;
      continue;
    }
    const mDays = minDaysToStockout(m);
    const worstDays = minDaysToStockout(worst);
    if (mDays < worstDays || (mDays === worstDays && m.facilityId < worst.facilityId)) worst = m;
  }
  return worst?.facilityId ?? null;
}

function hexToFeature(cell: HexCell, color: string): GeoJSON.Feature<GeoJSON.Polygon> {
  const ring = cell.boundary.map((p) => [p.lng, p.lat] as [number, number]);
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first && last && (first[0] !== last[0] || first[1] !== last[1])) ring.push(first);
  return {
    type: "Feature",
    properties: { hexId: cell.hexId, worstSeverity: cell.worstSeverity, facilityCount: cell.facilityCount, color },
    geometry: { type: "Polygon", coordinates: [ring] },
  };
}

const HEX_SOURCE_ID = "risk-hex-cells";
const HEX_LAYER_ID = "risk-hex-fill";

export function RiskMap({ markers, onSelect }: { markers: RiskMarker[]; onSelect?: (m: RiskMarker) => void }) {
  const { t } = useTranslation(["dashboard", "common"]);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const reducedMotion = useReducedMotion();
  const [pausedByUser, setPausedByUser] = useState(false);
  const [colors, setColors] = useState<Record<Severity, string>>(FALLBACK_SEVERITY_COLOR);
  const [hexCells, setHexCells] = useState<HexCell[]>([]);
  const [pulseTargetId, setPulseTargetId] = useState<string | null>(null);

  // A facility with no recorded coordinates (OPS-01's location is nullable) has nowhere to plot —
  // skipped here rather than guessing a fallback position.
  const located = useMemo(() => markers.filter((m): m is LocatedMarker => m.location !== null), [markers]);

  // --- severity colors: read once, and again whenever the light/dark toggle flips ---
  useEffect(() => {
    setColors(readSeverityColors());
    const observer = new MutationObserver(() => setColors(readSeverityColors()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  // --- hex choropleth data: single fixed resolution (the backend default), fetched once ---
  useEffect(() => {
    let cancelled = false;
    intelligence
      .getHexMap()
      .then((cells) => {
        if (!cancelled) setHexCells(cells);
      })
      .catch(() => {
        // Choropleth is a supplementary overlay — facility markers stay fully usable without it.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Placed under the facility markers: markers are DOM overlays MapLibre always paints above the
  // GL canvas, so this GL fill layer is already visually below them regardless of layer order.
  // Inserted before the first symbol (label) layer so place-name text still reads on top of it.
  const syncHexLayer = useCallback(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (map.getLayer(HEX_LAYER_ID)) map.removeLayer(HEX_LAYER_ID);
    if (map.getSource(HEX_SOURCE_ID)) map.removeSource(HEX_SOURCE_ID);
    if (hexCells.length === 0) return;

    const data: GeoJSON.FeatureCollection<GeoJSON.Polygon> = {
      type: "FeatureCollection",
      features: hexCells.map((cell) => hexToFeature(cell, colors[cell.worstSeverity])),
    };
    map.addSource(HEX_SOURCE_ID, { type: "geojson", data });
    const labelLayer = map.getStyle()?.layers?.find((l) => l.type === "symbol");
    map.addLayer(
      {
        id: HEX_LAYER_ID,
        type: "fill",
        source: HEX_SOURCE_ID,
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": 0.35,
          "fill-outline-color": ["get", "color"],
        },
      },
      labelLayer?.id
    );
  }, [hexCells, colors]);

  const syncHexLayerRef = useRef(syncHexLayer);
  useEffect(() => {
    syncHexLayerRef.current = syncHexLayer;
    if (mapRef.current?.isStyleLoaded()) syncHexLayer();
  }, [syncHexLayer]);

  const recomputePulse = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    setPulseTargetId(computePulseTarget(map, located));
  }, [located]);

  const recomputePulseRef = useRef(recomputePulse);
  useEffect(() => {
    recomputePulseRef.current = recomputePulse;
    if (mapRef.current) recomputePulse();
  }, [recomputePulse]);

  // --- map init: once on mount ---
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let styleLoadedOnce = false;
    let fallbackApplied = false;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: VECTOR_STYLE_URL,
      center: located[0] ? [located[0].location.lng, located[0].location.lat] : [80.63, 16.5],
      zoom: 10,
    });
    mapRef.current = map;

    map.on("load", () => {
      styleLoadedOnce = true;
      syncHexLayerRef.current();
      recomputePulseRef.current();
    });
    map.on("error", (e) => {
      // Only treat this as a basemap failure the first time, and only before the style has ever
      // loaded successfully — a later runtime tile 404 shouldn't blow away a working vector map.
      if (styleLoadedOnce || fallbackApplied) return;
      fallbackApplied = true;
      // eslint-disable-next-line no-console
      console.warn("RiskMap: vector basemap failed to load, falling back to OSM raster tiles.", e?.error);
      map.setStyle(OSM_FALLBACK_STYLE);
    });
    map.on("moveend", () => recomputePulseRef.current());

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- facility markers ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const pulseActive = !reducedMotion && !pausedByUser;

    const created: { marker: maplibregl.Marker; root: Root }[] = located.map((m) => {
      const wrap = document.createElement("button");
      wrap.type = "button";
      wrap.style.position = "relative";
      wrap.style.width = "20px";
      wrap.style.height = "20px";
      wrap.style.cursor = "pointer";
      wrap.style.background = "transparent";
      wrap.style.border = "none";
      wrap.style.padding = "0";
      wrap.style.transition = "transform 150ms ease-out";
      wrap.title = `${m.facilityName} — ${t(`common:severity.${m.worstSeverity}`)}`;
      wrap.setAttribute("aria-label", wrap.title);
      wrap.onmouseenter = () => (wrap.style.transform = "scale(1.35)");
      wrap.onmouseleave = () => (wrap.style.transform = "scale(1)");
      wrap.onclick = () => onSelect?.(m);

      const root = createRoot(wrap);
      root.render(
        <MarkerGlyph
          severity={m.worstSeverity}
          color={colors[m.worstSeverity]}
          pulsing={pulseActive && m.facilityId === pulseTargetId}
        />
      );

      const marker = new maplibregl.Marker({ element: wrap }).setLngLat([m.location.lng, m.location.lat]).addTo(map);
      return { marker, root };
    });

    return () => {
      created.forEach(({ marker, root }) => {
        marker.remove();
        root.unmount();
      });
    };
  }, [located, onSelect, colors, pulseTargetId, reducedMotion, pausedByUser, t]);

  return (
    <div className="relative w-full h-80 rounded-hig overflow-hidden border border-separator shadow-card animate-fade-in-up">
      <div ref={containerRef} className="w-full h-full" />
      {/* WCAG 2.2.2 (Pause, Stop, Hide): the map's rarity-budget pulse runs indefinitely once a
          CRITICAL outlier is in view, so it needs a visible pause control on top of (not instead
          of) honoring prefers-reduced-motion — shown only when there's something to pause. */}
      {!reducedMotion && pulseTargetId && (
        <MotionPauseControl
          paused={pausedByUser}
          onToggle={() => setPausedByUser((p) => !p)}
          label={t("dashboard:riskMapPulse")}
          className="absolute top-2 right-2 z-10"
        />
      )}
    </div>
  );
}
