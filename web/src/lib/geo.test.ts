import { describe, expect, it } from "vitest";
import { geoNote, parentMetricsNote } from "./geo";
import type { Metro } from "../types";

const base = { cbsa: "1", name: "x", lat: 0, lon: 0 } as unknown as Metro;

describe("geoNote", () => {
  it("says nothing for a plain metro", () => {
    expect(geoNote({ ...base, level: "msa", parent: null, zillow_scope: "metro" })).toBeNull();
  });

  it("names the parent and the zillow scope for a division", () => {
    const m = { ...base, level: "division", parent: { cbsa: "16980", name: "Chicago-Naperville-Elgin, IL-IN" }, zillow_scope: "parent metro" } as Metro;
    expect(geoNote(m)).toBe("Metropolitan division of Chicago-Naperville-Elgin, IL-IN. Zillow values are for the parent metro.");
  });

  it("skips the zillow sentence when there are no zillow values", () => {
    const m = { ...base, level: "division", parent: { cbsa: "16980", name: "Chicago" }, zillow_scope: null } as Metro;
    expect(geoNote(m)).toBe("Metropolitan division of Chicago.");
  });

  it("handles data without the new fields", () => {
    expect(geoNote(base)).toBeNull();
  });
});

describe("parentMetricsNote", () => {
  it("is null without inherited metrics", () => {
    expect(parentMetricsNote(base)).toBeNull();
    expect(parentMetricsNote({ ...base, parent_metrics: [] })).toBeNull();
  });

  it("lists inherited metrics by label, deduplicated, unknown keys as they are", () => {
    const m = { ...base, parent_metrics: ["permits_units", "inventory", "permits_units", "mystery"] };
    expect(parentMetricsNote(m)).toBe("From the parent metro: Housing units permitted, For sale inventory, mystery.");
  });
});
