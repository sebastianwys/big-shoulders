import { describe, expect, it } from "vitest";
import {
  DEFS, METRICS, PERIODS, availablePeriods, defById, labelFor, metricById, metricCaption, nearestPeriod, num,
  resolveMetric, visibleDefs,
} from "./metrics";
import type { Metro, Period } from "../types";
import { SAMPLE } from "./data";

const abilene = SAMPLE.metros[0];
const dallas = SAMPLE.metros[1];
const sparse = SAMPLE.metros[2];
const def = (id: string) => defById(id)!.def;

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

  it("never throw on an empty object at any period", () => {
    const empty = {} as Metro;
    for (const d of DEFS) {
      for (const p of [...PERIODS, null] as (Period | null)[]) {
        expect(() => d.valueAt(empty, p), `${d.id} at ${p}`).not.toThrow();
        expect(d.valueAt(empty, p), `${d.id} at ${p}`).toBeNull();
      }
    }
    for (const metric of METRICS) {
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

  it("read enrichment fields from year panels and from latest", () => {
    expect(def("gross_rent").valueAt(abilene, "2024")).toBe(1141);
    expect(def("permits_units").valueAt(abilene, "latest")).toBe(1160);
    expect(def("irs_net_returns").valueAt(abilene, "2024")).toBeNull();
  });
});

describe("periods", () => {
  it("resolve a legacy id into a definition and a period", () => {
    expect(defById("income_2024")).toMatchObject({ period: "2024" });
    expect(defById("zhvi_latest")).toMatchObject({ period: "latest" });
    expect(defById("hpi_19_24")).toMatchObject({ period: null });
    expect(defById("nothing_2024")).toBeNull();
  });

  it("label the resolved metric with its period, change metrics without", () => {
    expect(resolveMetric(def("gross_rent"), "2019").label).toBe("Median gross rent, 2019");
    expect(resolveMetric(def("permits_units"), "latest").label).toBe("Housing units permitted, latest");
    const change = resolveMetric(def("hpi_19_24"), "2024");
    expect(change.period).toBeNull();
    expect(change.id).toBe("hpi_19_24");
  });

  it("fall back to the default period when the asked one is not declared", () => {
    expect(resolveMetric(def("gross_rent"), "latest").period).toBe("2024");
    expect(resolveMetric(def("zhvf_forecast"), "2014").period).toBe("latest");
  });

  it("report only the declared periods that carry data", () => {
    expect(availablePeriods(def("irs_net_returns"), SAMPLE.metros)).toEqual(["2014", "2019", "latest"]);
    expect(availablePeriods(def("days_to_pending"), [dallas])).toEqual([]);
    expect(availablePeriods(def("gross_rent"), [])).toEqual(["2014", "2019", "2024"]);
  });

  it("pick the nearest available period, later on a tie", () => {
    expect(nearestPeriod("2024", ["2014", "2019", "latest"])).toBe("latest");
    expect(nearestPeriod("2014", ["2019", "2024"])).toBe("2019");
    expect(nearestPeriod("2019", ["2019", "2024"])).toBe("2019");
    expect(nearestPeriod(null, ["2014", "2019"])).toBe("2019");
    expect(nearestPeriod("latest", [])).toBeNull();
  });
});

describe("visibility", () => {
  it("hides a metric that is null for every metro and keeps one with a single value", () => {
    const ids = visibleDefs(SAMPLE.metros).map((d) => d.id);
    expect(ids).not.toContain("bea_income_per_capita");
    expect(ids).not.toContain("fmr_2br");
    expect(ids).toContain("gross_rent");
    expect(ids).toContain("hpi_19_24");
    const one = [{ ...sparse, latest: { ...sparse.latest, fmr_2br: 1200 } } as Metro];
    expect(visibleDefs(one).map((d) => d.id)).toContain("fmr_2br");
  });

  it("shows everything before data loads", () => {
    expect(visibleDefs([])).toHaveLength(DEFS.length);
  });
});

describe("derived metrics", () => {
  it("compute permits per thousand and rent to income", () => {
    expect(def("permits_per_1000").valueAt(abilene, "2024")).toBeCloseTo((527 / 183719) * 1000, 4);
    expect(def("rent_to_income").valueAt(abilene, "2024")).toBeCloseTo((1141 * 12) / 62010, 4);
  });

  it("return null when an input is missing or the population is zero", () => {
    const zero = { ...abilene, years: { ...abilene.years, "2024": { ...abilene.years["2024"], pop_estimate: 0 } } } as Metro;
    expect(def("permits_per_1000").valueAt(zero, "2024")).toBeNull();
    expect(def("permits_per_1000").valueAt(sparse, "2014")).toBeCloseTo((250 / 80000) * 1000, 4);
    expect(def("rent_to_income").valueAt(sparse, "2014")).toBeNull();
    expect(def("rent_to_income").valueAt(abilene, "latest")).toBeNull();
  });
});

describe("captions and labels", () => {
  it("name the source and the newest latest date across metros", () => {
    expect(metricCaption(resolveMetric(def("median_listing_price"), "latest"), SAMPLE.metros)).toBe("Source: Realtor.com, latest 2026-08");
    expect(metricCaption(resolveMetric(def("gross_rent"), "2019"), SAMPLE.metros)).toBe("Source: Census ACS, 2019");
    expect(metricCaption(resolveMetric(def("hpi_19_24"), null), SAMPLE.metros)).toBe("Source: FHFA");
    expect(metricCaption(resolveMetric(def("zhvf_forecast"), "latest"), [])).toBe("Source: Zillow, latest");
  });

  it("map a field key to its label and pass unknown keys through", () => {
    expect(labelFor("permits_units")).toBe("Housing units permitted");
    expect(labelFor("mystery")).toBe("mystery");
  });
});
