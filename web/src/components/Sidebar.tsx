import { useMemo, useState } from "react";
import { formatValue } from "../lib/format";
import { METRICS, type Metric } from "../lib/metrics";
import { rankMetros, searchMetros } from "../lib/rank";
import type { ColorScale } from "../lib/scale";
import type { MapData, Metro } from "../types";

interface Props {
  metros: Metro[];
  metric: Metric;
  scale: ColorScale;
  selectedCbsa: string | null;
  sources: MapData["sources"];
  generatedAt: string;
  onMetricChange: (id: string) => void;
  onSelect: (cbsa: string) => void;
}

export function Sidebar({ metros, metric, scale, selectedCbsa, sources, generatedAt, onMetricChange, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [showAll, setShowAll] = useState(false);

  const results = useMemo(() => searchMetros(metros, query), [metros, query]);
  const ranked = useMemo(() => rankMetros(metros, metric, showAll ? undefined : 15), [metros, metric, showAll]);
  const signed = metric.kind === "diverging";

  const pick = (metro: Metro) => {
    onSelect(metro.cbsa);
    setQuery("");
    setActive(0);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(results[Math.min(active, results.length - 1)]);
    } else if (e.key === "Escape") {
      setQuery("");
    }
  };

  return (
    <aside className="sidebar">
      <div>
        <label htmlFor="metric">color metros by</label>
        <select id="metric" value={metric.id} onChange={(e) => onMetricChange(e.target.value)}>
          {METRICS.map((m) => (
            <option key={m.id} value={m.id}>{m.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="search">find a metro</label>
        <input
          id="search"
          type="search"
          placeholder="type a metro name"
          value={query}
          autoComplete="off"
          onChange={(e) => { setQuery(e.target.value); setActive(0); }}
          onKeyDown={onKeyDown}
          aria-controls="search-results"
        />
        {results.length > 0 && (
          <ul className="results" id="search-results">
            {results.map((m, i) => (
              <li key={m.cbsa}>
                <button type="button" className={i === active ? "active" : ""} onClick={() => pick(m)}>
                  {m.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rank">
        <h2>{showAll ? `all ${ranked.length} metros` : "top 15"} by {metric.label.toLowerCase()}</h2>
        {showAll ? (
          <div className="table-all">
            <table>
              <thead>
                <tr><th>#</th><th>metro</th><th className="v">value</th></tr>
              </thead>
              <tbody>
                {ranked.map((r, i) => (
                  <tr key={r.metro.cbsa}>
                    <td>{i + 1}</td>
                    <td><button type="button" onClick={() => onSelect(r.metro.cbsa)}>{r.metro.name}</button></td>
                    <td className="v">{formatValue(r.value, metric.format, signed)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <ol>
            {ranked.map((r, i) => (
              <li key={r.metro.cbsa}>
                <button
                  type="button"
                  className={r.metro.cbsa === selectedCbsa ? "selected" : ""}
                  onClick={() => onSelect(r.metro.cbsa)}
                >
                  <span className="n">{i + 1}</span>
                  <span>
                    <span className="swatch" style={{ background: scale.color(r.value) }} aria-hidden="true" />
                    {r.metro.name}
                  </span>
                  <span className="v">{formatValue(r.value, metric.format, signed)}</span>
                </button>
              </li>
            ))}
          </ol>
        )}
        <button type="button" className="linkish" onClick={() => setShowAll((s) => !s)}>
          {showAll ? "show top 15" : "show all as a table"}
        </button>
      </div>

      <footer className="footer">
        <p>
          Vintages: Census Gazetteer {sources.gazetteer}; Zillow {sources.zillow ?? "not loaded"}; BLS {sources.bls ?? "not loaded"}; FRED {sources.fred ?? "not loaded"}. Built {generatedAt}.
        </p>
        <p>
          House prices: FHFA House Price Index. Demographics: U.S. Census Bureau, ACS 5-year estimates.
          Home values and rents: Data provided by Zillow Research. Unemployment: U.S. Bureau of Labor Statistics, LAUS.
          Mortgage rates: FRED, Federal Reserve Bank of St. Louis. Tiles: OpenStreetMap contributors.
        </p>
      </footer>
    </aside>
  );
}
