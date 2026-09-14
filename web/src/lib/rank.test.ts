import { describe, expect, it } from "vitest";
import { rankMetros, searchMetros } from "./rank";
import { metricById } from "./metrics";
import { SAMPLE } from "./data";

describe("rankMetros", () => {
  it("sorts descending and skips nulls", () => {
    const ranked = rankMetros(SAMPLE.metros, metricById("hpi_19_24"));
    expect(ranked.map((r) => r.metro.cbsa)).toEqual(["19100", "10180"]);
    expect(ranked[0].value).toBeGreaterThan(ranked[1].value);
  });

  it("respects the limit", () => {
    expect(rankMetros(SAMPLE.metros, metricById("pop_14_24"), 1)).toHaveLength(1);
  });

  it("is empty when nothing has a value", () => {
    const metric = { ...metricById("hpi_19_24"), accessor: () => null };
    expect(rankMetros(SAMPLE.metros, metric)).toEqual([]);
  });
});

describe("searchMetros", () => {
  it("matches partial names case insensitively", () => {
    expect(searchMetros(SAMPLE.metros, "abil").map((m) => m.cbsa)).toEqual(["10180"]);
    expect(searchMetros(SAMPLE.metros, "TX").map((m) => m.cbsa)).toEqual(["10180", "19100"]);
  });

  it("returns nothing for a blank query", () => {
    expect(searchMetros(SAMPLE.metros, "   ")).toEqual([]);
  });

  it("caps results", () => {
    expect(searchMetros(SAMPLE.metros, "a", 2)).toHaveLength(2);
  });
});
