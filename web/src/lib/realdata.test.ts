import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { METRICS } from "./metrics";
import { rankMetros } from "./rank";
import { buildScale } from "./scale";
import type { MapData } from "../types";

// the built json is optional in ci, so this suite skips when it is absent
const PATH = new URL("../../public/data/metros.json", import.meta.url).pathname;
const present = existsSync(PATH);
const data: MapData | null = present ? (JSON.parse(readFileSync(PATH, "utf8")) as MapData) : null;

describe.skipIf(!present)("built metros.json", () => {
  it("has the study shape", () => {
    expect(data!.years).toEqual([2014, 2019, 2024]);
    expect(data!.metros.length).toBeGreaterThan(300);
    for (const m of data!.metros) {
      expect(m.cbsa).toMatch(/^\d{5}$/);
      expect(Number.isFinite(m.lat) && Number.isFinite(m.lon)).toBe(true);
    }
  });

  it("builds a five class scale for every metric without nan", () => {
    for (const metric of METRICS) {
      const values = data!.metros.map(metric.accessor);
      const scale = buildScale(values, metric.kind);
      expect(scale.bins, metric.id).toHaveLength(5);
      for (const bin of scale.bins) {
        expect(Number.isFinite(bin.from) && Number.isFinite(bin.to), metric.id).toBe(true);
      }
      const covered = values.filter((v) => v !== null).length;
      expect(covered, `${metric.id} coverage`).toBeGreaterThan(data!.metros.length / 2);
    }
  });

  it("ranks the core metric across most metros", () => {
    const ranked = rankMetros(data!.metros, METRICS[0]);
    expect(ranked.length).toBeGreaterThan(300);
    expect(ranked[0].value).toBeGreaterThanOrEqual(ranked[ranked.length - 1].value);
  });
});
