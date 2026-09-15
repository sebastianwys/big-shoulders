import type { Topology } from "topojson-specification";
import { describe, expect, it } from "vitest";
import {
  NULL_FILL_OPACITY,
  SHAPE_FILL_OPACITY,
  decodeBoundaries,
  featureFor,
  shapeStyle,
  studyShapes,
} from "./boundaries";
import { INK, INK_2, NULL_GRAY, SEQUENTIAL, SURFACE } from "./palette";
import { buildScale } from "./scale";
import type { Metro } from "../types";

// one square arc shared by a metro and a division, no quantization transform
const topology: Topology = {
  type: "Topology",
  arcs: [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
  objects: {
    cbsa: {
      type: "GeometryCollection",
      geometries: [
        { type: "Polygon", arcs: [[0]], properties: { GEOID: "10180", NAME: "Abilene, TX" } },
        { type: "Polygon", arcs: [[0]], properties: { GEOID: "99999", NAME: "Not in the study" } },
      ],
    },
    metdiv: {
      type: "GeometryCollection",
      geometries: [
        { type: "Polygon", arcs: [[0]], properties: { GEOID: "16984", NAME: "Chicago-Naperville-Schaumburg, IL" } },
      ],
    },
  },
};

const metro = (cbsa: string, level?: "msa" | "division") =>
  ({ cbsa, name: cbsa, level, lat: 0, lon: 0 }) as unknown as Metro;

describe("decodeBoundaries", () => {
  it("keys each object by its five digit code and decodes the geometry", () => {
    const index = decodeBoundaries(topology);
    expect([...index.cbsa.keys()]).toEqual(["10180", "99999"]);
    expect([...index.metdiv.keys()]).toEqual(["16984"]);
    const abilene = index.cbsa.get("10180");
    expect(abilene?.properties.NAME).toBe("Abilene, TX");
    expect(abilene?.geometry.type).toBe("Polygon");
    expect((abilene?.geometry as { coordinates: number[][][] }).coordinates[0]).toHaveLength(5);
  });

  it("gives an empty map for a missing object instead of throwing", () => {
    const only = { ...topology, objects: { cbsa: topology.objects.cbsa } } as Topology;
    const index = decodeBoundaries(only);
    expect(index.cbsa.size).toBe(2);
    expect(index.metdiv.size).toBe(0);
  });
});

describe("featureFor", () => {
  const index = decodeBoundaries(topology);

  it("uses the cbsa object for a metro and the metdiv object for a division", () => {
    expect(featureFor(metro("10180", "msa"), index)?.properties.GEOID).toBe("10180");
    expect(featureFor(metro("16984", "division"), index)?.properties.GEOID).toBe("16984");
  });

  it("treats a metro without a level as a cbsa", () => {
    expect(featureFor(metro("10180"), index)?.properties.NAME).toBe("Abilene, TX");
  });

  it("returns null for a code with no feature and never crosses objects", () => {
    expect(featureFor(metro("00000", "msa"), index)).toBeNull();
    expect(featureFor(metro("16984", "msa"), index)).toBeNull();
    expect(featureFor(metro("10180", "division"), index)).toBeNull();
  });
});

describe("studyShapes", () => {
  it("draws only the study's metros, in study order", () => {
    const index = decodeBoundaries(topology);
    const shapes = studyShapes([metro("16984", "division"), metro("10180", "msa"), metro("00000", "msa")], index);
    expect(shapes.map((s) => s.metro.cbsa)).toEqual(["16984", "10180"]);
    expect(shapes.map((s) => s.feature.properties.GEOID)).toEqual(["16984", "10180"]);
  });

  it("is empty when nothing matches", () => {
    expect(studyShapes([metro("00000")], decodeBoundaries(topology))).toEqual([]);
  });
});

describe("shapeStyle", () => {
  const scale = buildScale([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "sequential");

  it("fills a number with the scale color under a surface hairline", () => {
    const style = shapeStyle(10, scale);
    expect(style.fillColor).toBe(SEQUENTIAL[4]);
    expect(style.fillOpacity).toBe(SHAPE_FILL_OPACITY);
    expect(style.color).toBe(SURFACE);
    expect(style.weight).toBe(1);
    expect(style.dashArray).toBeUndefined();
  });

  it("marks null with gray, low opacity and a dashed stroke, not color alone", () => {
    const style = shapeStyle(null, scale);
    expect(style.fillColor).toBe(NULL_GRAY);
    expect(style.fillOpacity).toBe(NULL_FILL_OPACITY);
    expect(style.dashArray).toBe("3 3");
    expect(style.color).toBe(NULL_GRAY);
  });

  it("treats a non finite value as null", () => {
    expect(shapeStyle(Number.NaN, scale).fillColor).toBe(NULL_GRAY);
  });

  it("lifts on hover and outlines the selected shape in ink", () => {
    const hover = shapeStyle(5, scale, { hover: true });
    expect(hover.color).toBe(INK_2);
    expect(hover.fillOpacity).toBeGreaterThan(SHAPE_FILL_OPACITY);
    const selected = shapeStyle(null, scale, { selected: true, hover: true });
    expect(selected.color).toBe(INK);
    expect(selected.weight).toBe(2.5);
    expect(selected.dashArray).toBeUndefined();
  });

  it("stays gray when the whole scale is empty", () => {
    expect(shapeStyle(3, buildScale([null], "sequential")).fillColor).toBe(NULL_GRAY);
  });
});
