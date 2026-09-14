export interface SparkPoint {
  x: number;
  y: number;
  value: number;
  index: number;
}

export interface Spark {
  d: string;
  points: SparkPoint[];
  width: number;
  height: number;
}

const r1 = (v: number) => Math.round(v * 10) / 10;

// path segments only join consecutive present values, so a null in the
// middle leaves a gap instead of bridging it
export function buildSparkline(values: (number | null)[], width = 160, height = 48, pad = 8): Spark {
  const present = values
    .map((v, i) => ({ v, i }))
    .filter((p): p is { v: number; i: number } => typeof p.v === "number" && Number.isFinite(p.v));
  if (present.length === 0) return { d: "", points: [], width, height };

  const n = values.length;
  const min = Math.min(...present.map((p) => p.v));
  const max = Math.max(...present.map((p) => p.v));
  const x = (i: number) => (n === 1 ? width / 2 : pad + (i * (width - 2 * pad)) / (n - 1));
  const y = (v: number) => (max === min ? height / 2 : height - pad - ((v - min) * (height - 2 * pad)) / (max - min));

  const points = present.map((p) => ({ x: r1(x(p.i)), y: r1(y(p.v)), value: p.v, index: p.i }));
  let d = "";
  points.forEach((p, k) => {
    const prev = points[k - 1];
    const next = points[k + 1];
    if (prev && p.index === prev.index + 1) d += ` L ${p.x} ${p.y}`;
    else if (next && next.index === p.index + 1) d += ` M ${p.x} ${p.y}`;
  });
  return { d: d.trim(), points, width, height };
}
