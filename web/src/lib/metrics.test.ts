import { describe, expect, it } from "vitest";
import { METRICS, metricById, num } from "./metrics";
import type { Metro } from "../types";
import { SAMPLE } from "./data";

const abilene = SAMPLE.metros[0];
const sparse = SAMPLE.metros[2];

describe("metric accessors", () => {
  it("return numbers for a complete metro", () => {
    expect(metricById("hpi_19_24").accessor(abilene)).toBeCloseTo(0.3291);
    expect(metricById("ptir_2024").accessor(abilene)).toBeCloseTo(2.67);
    expect(metricById("income_2024").accessor(abilene)).toBe(62010);
  });

  it("return null where the field is null", () => {
    expect(metricById("hpi_19_24").accessor(sparse)).toBeNull();
    expect(metricById("zhvi_latest").accessor(sparse)).toBeNull();
    expect(metricById("ptir_2024").accessor(sparse)).toBeNull();
  });

  it("never throw on an empty object", () => {
    const empty = {} as Metro;
    for (const metric of METRICS) {
      expect(() => metric.accessor(empty)).not.toThrow();
      expect(metric.accessor(empty)).toBeNull();
    }
  });

  it("treat nan and strings as missing", () => {
    expect(num(Number.NaN)).toBeNull();
    expect(num("12")).toBeNull();
    expect(num(12)).toBe(12);
  });

  it("fall back to the first metric for an unknown id", () => {
    expect(metricById("nope").id).toBe(METRICS[0].id);
  });
});
