import { formatValue } from "../lib/format";
import type { Metric } from "../lib/metrics";
import type { ColorScale } from "../lib/scale";

interface Props {
  scale: ColorScale;
  metric: Metric;
}

export function Legend({ scale, metric }: Props) {
  const signed = scale.kind === "diverging";
  return (
    <div className="legend" role="group" aria-label="map legend">
      <div className="title">{metric.label}</div>
      {scale.bins.map((bin, i) => (
        <div className="row" key={i}>
          <span className="sw" style={{ background: bin.color }} />
          <span>
            {formatValue(bin.from, metric.format, signed)} to {formatValue(bin.to, metric.format, signed)}
          </span>
        </div>
      ))}
      <div className="row">
        <span className="sw null" />
        <span>no data</span>
      </div>
    </div>
  );
}
