import { formatValue } from "../lib/format";
import type { ValueFormat } from "../lib/metrics";
import type { Growth, Metro, YearKey, YearValues } from "../types";
import { Sparkline } from "./Sparkline";

const YEARS: YearKey[] = ["2014", "2019", "2024"];

const ROWS: { key: keyof YearValues; label: string; format: ValueFormat }[] = [
  { key: "hpi", label: "House price index", format: "index" },
  { key: "income", label: "Median household income", format: "usd" },
  { key: "home_value", label: "Median home value", format: "usd" },
  { key: "pop", label: "Population", format: "int" },
  { key: "age", label: "Median age", format: "index" },
  { key: "degree_share", label: "Bachelors or masters share", format: "pct" },
  { key: "own_rate", label: "Homeownership rate", format: "pct" },
  { key: "zhvi", label: "Zillow home value index", format: "usd" },
  { key: "zori", label: "Zillow rent index", format: "usd" },
  { key: "unemp", label: "Unemployment rate", format: "rate" },
];

const GROWTH: { key: keyof Growth; label: string }[] = [
  { key: "hpi_14_19", label: "HPI, 2014 to 2019" },
  { key: "hpi_19_24", label: "HPI, 2019 to 2024" },
  { key: "income_14_24", label: "Median income, 2014 to 2024" },
  { key: "home_value_14_24", label: "Median home value, 2014 to 2024" },
  { key: "pop_14_24", label: "Population, 2014 to 2024" },
];

interface Props {
  metro: Metro;
  onClose: () => void;
}

export function DetailPanel({ metro, onClose }: Props) {
  const year = (y: YearKey, key: keyof YearValues) => metro.years?.[y]?.[key] ?? null;
  const latest = metro.latest ?? { zhvi: null, zhvi_date: null, zori: null, zori_date: null, unemp: null, unemp_date: null };

  return (
    <aside className="detail" aria-label={`${metro.name} detail`}>
      <header>
        <h2>{metro.name}</h2>
        <button className="close" aria-label="close detail" onClick={onClose}>
          x
        </button>
      </header>

      <h3>House price index, all transactions</h3>
      <Sparkline
        values={YEARS.map((y) => year(y, "hpi"))}
        labels={YEARS}
        title={`house price index for ${metro.name}, 2014, 2019 and 2024`}
      />

      <h3>By vintage year</h3>
      <table>
        <thead>
          <tr>
            <th>measure</th>
            {YEARS.map((y) => <th key={y}>{y}</th>)}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              {YEARS.map((y) => <td key={y}>{formatValue(year(y, row.key), row.format)}</td>)}
            </tr>
          ))}
          <tr>
            <td>Price to income ratio</td>
            {YEARS.map((y) => <td key={y}>{formatValue(metro.ptir?.[y] ?? null, "ratio")}</td>)}
          </tr>
        </tbody>
      </table>

      <h3>Change</h3>
      <table>
        <tbody>
          {GROWTH.map((g) => (
            <tr key={g.key}>
              <td>{g.label}</td>
              <td>{formatValue(metro.growth?.[g.key] ?? null, "pct", true)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Latest</h3>
      <table>
        <tbody>
          <tr>
            <td>Zillow home value index</td>
            <td>{formatValue(latest.zhvi, "usd")}</td>
            <td>{latest.zhvi_date ?? "-"}</td>
          </tr>
          <tr>
            <td>Zillow rent index</td>
            <td>{formatValue(latest.zori, "usd")}</td>
            <td>{latest.zori_date ?? "-"}</td>
          </tr>
          <tr>
            <td>Unemployment rate</td>
            <td>{formatValue(latest.unemp, "rate")}</td>
            <td>{latest.unemp_date ?? "-"}</td>
          </tr>
        </tbody>
      </table>
    </aside>
  );
}
