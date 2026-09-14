import type { Metro, YearKey, YearValues } from "../types";

export type ScaleKind = "sequential" | "diverging";
export type ValueFormat = "pct" | "usd" | "ratio" | "rate" | "int" | "index";

export interface Metric {
  id: string;
  label: string;
  format: ValueFormat;
  kind: ScaleKind;
  accessor: (metro: Metro) => number | null;
}

// a value is usable only if it is a finite number
export function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function yearValue(metro: Metro, year: YearKey, field: keyof YearValues): number | null {
  return num(metro?.years?.[year]?.[field]);
}

export const METRICS: Metric[] = [
  { id: "hpi_19_24", label: "HPI growth, 2019 to 2024", format: "pct", kind: "diverging", accessor: (m) => num(m?.growth?.hpi_19_24) },
  { id: "hpi_14_19", label: "HPI growth, 2014 to 2019", format: "pct", kind: "diverging", accessor: (m) => num(m?.growth?.hpi_14_19) },
  { id: "ptir_2024", label: "Price to income ratio, 2024", format: "ratio", kind: "sequential", accessor: (m) => num(m?.ptir?.["2024"]) },
  { id: "income_2024", label: "Median household income, 2024", format: "usd", kind: "sequential", accessor: (m) => yearValue(m, "2024", "income") },
  { id: "home_value_2024", label: "Median home value, 2024", format: "usd", kind: "sequential", accessor: (m) => yearValue(m, "2024", "home_value") },
  { id: "zhvi_latest", label: "Zillow home value index, latest", format: "usd", kind: "sequential", accessor: (m) => num(m?.latest?.zhvi) },
  { id: "zori_latest", label: "Zillow rent index, latest", format: "usd", kind: "sequential", accessor: (m) => num(m?.latest?.zori) },
  { id: "unemp_latest", label: "Unemployment rate, latest", format: "rate", kind: "sequential", accessor: (m) => num(m?.latest?.unemp) },
  { id: "pop_14_24", label: "Population growth, 2014 to 2024", format: "pct", kind: "diverging", accessor: (m) => num(m?.growth?.pop_14_24) },
  { id: "degree_2024", label: "Bachelors or masters share, 2024", format: "pct", kind: "sequential", accessor: (m) => yearValue(m, "2024", "degree_share") },
  { id: "own_2024", label: "Homeownership rate, 2024", format: "pct", kind: "sequential", accessor: (m) => yearValue(m, "2024", "own_rate") },
];

export function metricById(id: string): Metric {
  return METRICS.find((m) => m.id === id) ?? METRICS[0];
}
