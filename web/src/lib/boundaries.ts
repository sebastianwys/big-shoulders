import type { Feature, Geometry } from "geojson";
import type { PathOptions } from "leaflet";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import type { Metro } from "../types";
import { INK, INK_2, NULL_GRAY, SURFACE } from "./palette";
import type { ColorScale } from "./scale";

export type MapMode = "dots" | "shapes";

export interface BoundaryProps {
  GEOID: string;
  NAME: string;
}

export type BoundaryFeature = Feature<Geometry, BoundaryProps>;

// the two topojson objects, each keyed by its five digit code
export interface BoundaryIndex {
  cbsa: Map<string, BoundaryFeature>;
  metdiv: Map<string, BoundaryFeature>;
}

export interface Shape {
  metro: Metro;
  feature: BoundaryFeature;
}

// one topojson object to features keyed by GEOID. a missing object gives an
// empty map rather than a throw, so a file with only cbsas still draws
function decodeObject(topology: Topology, name: string): Map<string, BoundaryFeature> {
  const out = new Map<string, BoundaryFeature>();
  const object = topology.objects[name] as GeometryCollection<BoundaryProps> | undefined;
  if (!object) return out;
  for (const f of feature(topology, object).features) {
    const code = f.properties?.GEOID;
    if (code) out.set(String(code), f as BoundaryFeature);
  }
  return out;
}

export function decodeBoundaries(topology: Topology): BoundaryIndex {
  return { cbsa: decodeObject(topology, "cbsa"), metdiv: decodeObject(topology, "metdiv") };
}

// a division draws its metdiv shape, everything else its cbsa shape. there is
// no cross lookup, so a division code never picks up a metro polygon
export function featureFor(metro: Pick<Metro, "cbsa" | "level">, index: BoundaryIndex): BoundaryFeature | null {
  const source = metro.level === "division" ? index.metdiv : index.cbsa;
  return source.get(metro.cbsa) ?? null;
}

// only the study's metros get a shape. codes in the file but not in the
// study are never drawn
export function studyShapes(metros: Metro[], index: BoundaryIndex): Shape[] {
  const shapes: Shape[] = [];
  for (const metro of metros) {
    const f = featureFor(metro, index);
    if (f) shapes.push({ metro, feature: f });
  }
  return shapes;
}

export const SHAPE_FILL_OPACITY = 0.72;
export const NULL_FILL_OPACITY = 0.35;

// the fill a dot would get. a surface colored hairline is the gap between
// touching fills. null is gray, faint and dashed, so no data never rides on
// color alone. hover lifts the shape, the selected one wears the ink outline
export function shapeStyle(
  value: number | null,
  scale: ColorScale,
  state: { selected?: boolean; hover?: boolean } = {},
): PathOptions {
  const missing = value === null || !Number.isFinite(value);
  const style: PathOptions = {
    fillColor: scale.color(value),
    fillOpacity: missing ? NULL_FILL_OPACITY : SHAPE_FILL_OPACITY,
    color: missing ? NULL_GRAY : SURFACE,
    weight: 1,
    dashArray: missing ? "3 3" : undefined,
  };
  if (state.hover) {
    style.color = INK_2;
    style.weight = 1.5;
    style.fillOpacity = missing ? NULL_FILL_OPACITY + 0.1 : SHAPE_FILL_OPACITY + 0.13;
  }
  if (state.selected) {
    style.color = INK;
    style.weight = 2.5;
    style.dashArray = undefined;
  }
  return style;
}

let cached: Promise<BoundaryIndex | null> | null = null;

// fetched once, the first time shapes are asked for. null when the file is
// missing, which the sidebar reports
export function loadBoundaries(): Promise<BoundaryIndex | null> {
  if (!cached) {
    cached = fetch(`${import.meta.env.BASE_URL}data/boundaries.json`)
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        return decodeBoundaries((await response.json()) as Topology);
      })
      .catch(() => null);
  }
  return cached;
}
