import { geoNote, parentMetricsNote } from "../lib/geo";
import { forecastCaption, forecastLines } from "../lib/forecast";
import { formatValue } from "../lib/format";
import { DEFS, GROUPS, dateAt, type MetricDef } from "../lib/metrics";
import type { Growth, Metro, YearKey } from "../types";
import { Sparkline } from "./Sparkline";

const YEARS: YearKey[] = ["2014", "2019", "2024"];

const GROWTH: { key: keyof Growth; label: string }[] = [
  { key: "hpi_14_19", label: "HPI, 2014 to 2019" },
  { key: "hpi_19_24", label: "HPI, 2019 to 2024" },
  { key: "income_14_24", label: "Median income, 2014 to 2024" },
  { key: "home_value_14_24", label: "Median home value, 2014 to 2024" },
  { key: "pop_14_24", label: "Population, 2014 to 2024" },
];

// the definitions in a group that are read by year and have a value in at
// least one of this metro's panels, so an uncollected source adds no rows
export function yearRows(metro: Metro, group: string): MetricDef[] {
  return DEFS.filter(
    (d) => d.group === group && d.periods.some((p) => p !== "latest") && YEARS.some((y) => d.valueAt(metro, y) !== null),
  );
}

// definitions with a latest value for this metro. the forecasts have a
// section of their own, with the bands
export function latestRows(metro: Metro): MetricDef[] {
  return DEFS.filter((d) => d.group !== "Forecasts" && d.periods.includes("latest") && d.valueAt(metro, "latest") !== null);
}

interface Props {
  metro: Metro;
  onClose: () => void;
}

export function DetailPanel({ metro, onClose }: Props) {
  const hpi = YEARS.map((y) => metro.years?.[y]?.hpi ?? null);
  const latest = latestRows(metro);
  const forecasts = forecastLines(metro);
  const inherited = parentMetricsNote(metro);

  return (
    <aside className="detail" aria-label={`${metro.name} detail`}>
      <header>
        <h2>{metro.name}</h2>
        {geoNote(metro) && <p className="geo-note">{geoNote(metro)}</p>}
        <button className="close" aria-label="close detail" onClick={onClose}>
          x
        </button>
      </header>

      <h3>House price index, all transactions</h3>
      <Sparkline values={hpi} labels={YEARS} title={`house price index for ${metro.name}, 2014, 2019 and 2024`} />

      {GROUPS.map((group) => {
        const rows = yearRows(metro, group);
        if (rows.length === 0) return null;
        return (
          <details key={group} open={group === "House prices"}>
            <summary>{group}, by vintage year</summary>
            <table>
              <thead>
                <tr>
                  <th>measure</th>
                  {YEARS.map((y) => <th key={y}>{y}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id}>
                    <td>{d.label}</td>
                    {YEARS.map((y) => (
                      <td key={y}>{formatValue(d.valueAt(metro, y), d.format, d.kind === "diverging")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        );
      })}

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

      {forecasts.length > 0 && (
        <>
          <h3>Forecasts</h3>
          <table>
            <tbody>
              {forecasts.map((line) => (
                <tr key={line.id}>
                  <td>{line.label}</td>
                  <td>{line.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="geo-note">{forecastCaption(metro)}</p>
        </>
      )}

      {latest.length > 0 && (
        <>
          <h3>Latest</h3>
          <table>
            <tbody>
              {latest.map((d) => (
                <tr key={d.id}>
                  <td>{d.label}</td>
                  <td>{formatValue(d.valueAt(metro, "latest"), d.format, d.kind === "diverging")}</td>
                  <td>{dateAt(metro, "latest", d.id) ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {inherited && <p className="geo-note">{inherited}</p>}
    </aside>
  );
}
