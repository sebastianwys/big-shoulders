import { describe, expect, it } from "vitest";
import { formatValue } from "./format";

describe("formatValue", () => {
  it("renders null as a dash for every format", () => {
    for (const f of ["pct", "usd", "usd_k", "ratio", "rate", "int", "index", "days", "minutes", "per_1000"] as const) {
      expect(formatValue(null, f)).toBe("-");
      expect(formatValue(Number.NaN, f)).toBe("-");
    }
  });

  it("formats each kind", () => {
    expect(formatValue(0.2081, "pct")).toBe("20.8%");
    expect(formatValue(44249, "usd")).toBe("$44,249");
    expect(formatValue(1234567, "usd")).toBe("$1.23M");
    expect(formatValue(2.08, "ratio")).toBe("2.1x");
    expect(formatValue(3.4, "rate")).toBe("3.4%");
    expect(formatValue(167171, "int")).toBe("167,171");
    expect(formatValue(186.892, "index")).toBe("186.9");
  });

  it("formats the enrichment kinds", () => {
    expect(formatValue(1234, "usd_k")).toBe("$1.23M");
    expect(formatValue(12, "usd_k")).toBe("$12,000");
    expect(formatValue(63.4, "days")).toBe("63 days");
    expect(formatValue(18.5, "minutes")).toBe("18.5 min");
    expect(formatValue(0.969, "per_1000")).toBe("1.0 per 1k");
  });

  it("signs positive values only when asked", () => {
    expect(formatValue(0.1, "pct", true)).toBe("+10.0%");
    expect(formatValue(-0.1, "pct", true)).toBe("-10.0%");
    expect(formatValue(0.1, "pct")).toBe("10.0%");
    expect(formatValue(15000, "int", true)).toBe("+15,000");
    expect(formatValue(-1.2, "per_1000", true)).toBe("-1.2 per 1k");
    expect(formatValue(0, "int", true)).toBe("0");
  });
});
