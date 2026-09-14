import type { MortgageRate } from "../types";

interface Props {
  rate: MortgageRate | null;
  sample: boolean;
}

export function Header({ rate, sample }: Props) {
  return (
    <header className="header">
      <h1>
        Big Shoulders
        <span className="sub">metro housing affordability, 2014 to 2024</span>
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
