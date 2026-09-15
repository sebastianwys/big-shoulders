import * as L from "leaflet";
import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { formatValue } from "../lib/format";
import type { Metric } from "../lib/metrics";
import { INK, NULL_GRAY, SURFACE } from "../lib/palette";
import type { ColorScale } from "../lib/scale";
import type { Metro } from "../types";
import { studyShapes, type BoundaryIndex, type MapMode } from "../lib/boundaries";
import { ShapeLayer } from "./ShapeLayer";

const CENTER: [number, number] = [39.5, -98.35];
const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

// area proportional to population, clamped so small metros stay clickable
export function markerRadius(pop: number | null): number {
  if (pop === null || !Number.isFinite(pop) || pop <= 0) return 5;
  return Math.min(22, Math.max(4, 0.0072 * Math.sqrt(pop)));
}

// pan only when the selection is off screen, so clicking a marker does not move the map
function FlyTo({ metro }: { metro: Metro | null }) {
  const map = useMap();
  useEffect(() => {
    if (!metro) return;
    const target = L.latLng(metro.lat, metro.lon);
    if (!map.getBounds().contains(target)) {
      map.flyTo(target, Math.max(map.getZoom(), 6), { duration: 0.6 });
    }
  }, [map, metro]);
  return null;
}

interface Props {
  metros: Metro[];
  metric: Metric;
  scale: ColorScale;
  selectedCbsa: string | null;
  onSelect: (cbsa: string) => void;
  mode: MapMode;
  boundaries: BoundaryIndex | null;
}

export function MapView({ metros, metric, scale, selectedCbsa, onSelect, mode, boundaries }: Props) {
  // canvas with a hit tolerance so a 4px dot has a 24px target
  const renderer = useMemo(() => L.canvas({ tolerance: 8 }), []);
  // big metros first so small ones draw on top
  const ordered = useMemo(
    () => [...metros].sort((a, b) => (b.years?.["2024"]?.pop ?? 0) - (a.years?.["2024"]?.pop ?? 0)),
    [metros],
  );
  const selected = metros.find((m) => m.cbsa === selectedCbsa) ?? null;
  const signed = metric.kind === "diverging";
  // dots stay up until the shapes are decoded, then the layers swap, never both
  const shapes = useMemo(() => (boundaries ? studyShapes(metros, boundaries) : []), [metros, boundaries]);
  const drawShapes = mode === "shapes" && shapes.length > 0;

  return (
    <MapContainer center={CENTER} zoom={4} minZoom={3} renderer={renderer} preferCanvas scrollWheelZoom>
      <TileLayer attribution={OSM_ATTRIBUTION} url={OSM} />
      {drawShapes && (
        <ShapeLayer shapes={shapes} metric={metric} scale={scale} selectedCbsa={selectedCbsa} onSelect={onSelect} />
      )}
      {!drawShapes && ordered.map((m) => {
        const value = metric.accessor(m);
        const missing = value === null;
        const isSelected = m.cbsa === selectedCbsa;
        return (
          <CircleMarker
            key={m.cbsa}
            center={[m.lat, m.lon]}
            radius={markerRadius(m.years?.["2024"]?.pop ?? null)}
            pathOptions={{
              color: isSelected ? INK : missing ? NULL_GRAY : SURFACE,
              weight: isSelected ? 3 : 2,
              dashArray: missing ? "3 3" : undefined,
              fillColor: scale.color(value),
              fillOpacity: missing ? 0.35 : 0.85,
            }}
            eventHandlers={{ click: () => onSelect(m.cbsa) }}
          >
            <Tooltip className="bs-tip" direction="top" offset={[0, -6]}>
              <span className="tv">{formatValue(value, metric.format, signed)}</span>{" "}
              <span className="tn">{m.name}</span>
            </Tooltip>
          </CircleMarker>
        );
      })}
      <FlyTo metro={selected} />
    </MapContainer>
  );
}
