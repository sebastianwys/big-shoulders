import { describe, expect, it } from "vitest";
import { formatValue } from "./format";

describe("formatValue", () => {
  it("renders null as a dash for every format", () => {
    for (const f of ["pct", "usd", "ratio", "rate", "int", "index"] as const) {
      expect(formatValue(null, f)).toBe("-");
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

  it("signs positive growth only when asked", () => {
    expect(formatValue(0.1, "pct", true)).toBe("+10.0%");
    expect(formatValue(-0.1, "pct", true)).toBe("-10.0%");
    expect(formatValue(0.1, "pct")).toBe("10.0%");
  });
});
