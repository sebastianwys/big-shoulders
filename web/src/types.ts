export type YearKey = "2014" | "2019" | "2024";

// the panels a metric can be read at. latest is the newest period a source
// publishes, which differs by source and is dated per value
export type Period = YearKey | "latest";

// every field the bot's enrichment sources add. each appears as an optional
// number in the year panels and in latest, with a sibling <key>_date in latest
export type EnrichmentKey =
  // census acs extras
  | "gross_rent" | "rent_burden" | "vacancy_rate" | "commute_minutes" | "poverty_rate" | "labor_force_rate"
  // census population estimates
  | "pop_estimate" | "natural_change" | "domestic_migration" | "net_migration" | "domestic_migration_rate"
  // census building permits
  | "permits_units" | "permits_single_family" | "permits_multifamily"
  // irs county migration
  | "irs_net_returns" | "irs_net_exemptions" | "irs_inflow_returns" | "irs_outflow_returns"
  // realtor.com listings
  | "median_listing_price" | "active_listings" | "days_on_market" | "price_reduced_share"
  // zillow extras
  | "inventory" | "days_to_pending" | "price_cut_share" | "zhvf_forecast"
  // bea, once a key is configured
  | "bea_income_per_capita" | "bea_personal_income"
  // hud, once a token is configured
  | "fmr_2br" | "median_family_income";

export type EnrichmentValues = { [K in EnrichmentKey]?: number | null };
export type EnrichmentDates = { [K in EnrichmentKey as `${K}_date`]?: string | null };

export interface YearValues extends EnrichmentValues {
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

export interface Latest extends EnrichmentValues, EnrichmentDates {
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

export interface ParentMetro {
  cbsa: string;
  name: string;
}

export interface Metro {
  cbsa: string;
  name: string;
  // metropolitan divisions are the pieces fhfa publishes for the largest metros
  level?: "msa" | "division";
  parent?: ParentMetro | null;
  // zillow publishes metros only, so a division carries its parent's values
  zillow_scope?: "metro" | "parent metro" | null;
  // enrichment metrics a division took from its parent metro
  parent_metrics?: string[];
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

// one version string per source folder the bot found, keyed by folder name
export interface Sources {
  gazetteer: string;
  zillow: string | null;
  bls: string | null;
  fred: string | null;
  [source: string]: string | null;
}

export interface MapData {
  generated_at: string;
  years: number[];
  sources: Sources;
  national: { mortgage_rate: MortgageRate | null };
  metros: Metro[];
}
