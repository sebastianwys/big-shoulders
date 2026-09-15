import { showMortgageStat } from "../lib/indicators";
import type { Indicator, MortgageRate } from "../types";
import { NationalStrip } from "./NationalStrip";

interface Props {
  rate: MortgageRate | null;
  sample: boolean;
  count?: number;
  indicators?: Indicator[];
  updated?: string | null;
}

// the subtitle names what the menu holds. the metro count comes from the
// loaded data so it never goes stale. the national figures sit under the
// title line, and the standalone rate stat stands in for them while a
// build carries no indicators
export function Header({ rate, sample, count = 0, indicators = [], updated = null }: Props) {
  const where = count > 0 ? `${count} U.S. metros` : "U.S. metros";
  return (
    <header className="header">
      <div className="title-row">
        <h1>
          Loop
          <span className="sub">housing, income, jobs and migration across {where}</span>
        </h1>
        {rate && showMortgageStat(rate, indicators) && (
          <div className="stat" aria-label="national 30 year mortgage rate">
            <span className="label">30-year mortgage rate, national</span>
            <span className="value">{rate.latest.toFixed(2)}%</span>
            <span className="note">as of {rate.latest_date}</span>
          </div>
        )}
        {indicators.length > 0 && updated && <span className="stamp">national figures as of {updated}</span>}
        {sample && <span className="badge">sample data</span>}
      </div>
      <NationalStrip indicators={indicators} />
    </header>
  );
}
