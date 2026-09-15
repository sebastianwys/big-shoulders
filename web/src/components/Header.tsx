import type { MortgageRate } from "../types";

interface Props {
  rate: MortgageRate | null;
  sample: boolean;
  count?: number;
}

// the subtitle names what the menu holds. the metro count comes from the
// loaded data so it never goes stale
export function Header({ rate, sample, count = 0 }: Props) {
  const where = count > 0 ? `${count} U.S. metros` : "U.S. metros";
  return (
    <header className="header">
      <h1>
        Loop
        <span className="sub">housing, income, jobs and migration across {where}</span>
      </h1>
      {rate && (
        <div className="stat" aria-label="national 30 year mortgage rate">
          <span className="label">30-year mortgage rate, national</span>
          <span className="value">{rate.latest.toFixed(2)}%</span>
          <span className="note">as of {rate.latest_date}</span>
        </div>
      )}
      {sample && <span className="badge">sample data</span>}
    </header>
  );
}
