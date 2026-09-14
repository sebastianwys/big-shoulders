import { describe, expect, it } from "vitest";
import { buildSparkline } from "./sparkline";

describe("buildSparkline", () => {
  it("centers a single point and draws no line", () => {
    const spark = buildSparkline([5], 100, 40);
    expect(spark.d).toBe("");
    expect(spark.points).toHaveLength(1);
    expect(spark.points[0].x).toBe(50);
    expect(spark.points[0].y).toBe(20);
  });

  it("joins two points with one segment", () => {
    const spark = buildSparkline([1, 2], 100, 40);
    expect(spark.d).toMatch(/^M [\d.]+ [\d.]+ L [\d.]+ [\d.]+$/);
    expect(spark.points[1].y).toBeLessThan(spark.points[0].y);
  });

  it("joins three points with two segments", () => {
    const spark = buildSparkline([1, 3, 2]);
    expect(spark.d.split(" L ")).toHaveLength(3);
  });

  it("leaves a gap around a null in the middle", () => {
    const spark = buildSparkline([1, null, 3]);
    expect(spark.d).toBe("");
    expect(spark.points.map((p) => p.index)).toEqual([0, 2]);
  });

  it("keeps the segment that precedes a trailing null", () => {
    const spark = buildSparkline([1, 2, null]);
    expect(spark.d).toMatch(/^M .* L /);
    expect(spark.points).toHaveLength(2);
  });

  it("returns nothing for all nulls", () => {
    expect(buildSparkline([null, null])).toMatchObject({ d: "", points: [] });
  });

  it("does not produce nan on constant values", () => {
    const spark = buildSparkline([4, 4, 4], 100, 40);
    spark.points.forEach((p) => {
      expect(Number.isFinite(p.y)).toBe(true);
      expect(p.y).toBe(20);
    });
  });
});
