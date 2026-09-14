export type YearKey = "2014" | "2019" | "2024";

export interface YearValues {
  hpi: number | null;
  income: number | null;
  pop: number | null;
  age: number | null;
  degree_share: number | null;
  own_rate: number | null;
  home_value: number | null;
  zhvi: number | null;
  zori: number | null;
  unemp: number | null;
}

export interface Latest {
  zhvi: number | null;
  zhvi_date: string | null;
  zori: number | null;
  zori_date: string | null;
  unemp: number | null;
  unemp_date: string | null;
}

export interface Growth {
  hpi_14_19: number | null;
  hpi_19_24: number | null;
  income_14_24: number | null;
  pop_14_24: number | null;
  home_value_14_24: number | null;
}

export interface Metro {
  cbsa: string;
  name: string;
  lat: number;
  lon: number;
  years: Record<YearKey, YearValues>;
  latest: Latest;
  growth: Growth;
  ptir: Record<YearKey, number | null>;
}

export interface MortgageRate {
  "2014": number;
  "2019": number;
  "2024": number;
  latest: number;
  latest_date: string;
}

export interface MapData {
  generated_at: string;
  years: number[];
  sources: {
    gazetteer: string;
    zillow: string | null;
    bls: string | null;
    fred: string | null;
  };
  national: { mortgage_rate: MortgageRate | null };
  metros: Metro[];
}
