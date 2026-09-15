import { describe, expect, it } from "vitest";
import { geoNote } from "./geo";
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
