import { useEffect, useMemo, useRef, useState } from "react";
import type { MetricDef } from "../lib/metrics";
import { buildTimeline, nextPeriod, prevPeriod, type TimelineTick } from "../lib/timeline";
import type { Metro, Period } from "../types";

interface Props {
  def: MetricDef;
  metros: Metro[];
  period: Period | null;
  available: Period[];
  onPeriodChange: (period: Period) => void;
}

// milliseconds each period stays on the map while playing
export const PLAY_MS = 1200;

const pct = (t: number) => `${(t * 100).toFixed(2)}%`;

function tickTitle(tick: TimelineTick, total: number): string {
  if (!tick.available) return "not published for this period";
  const when = tick.period === "latest" && tick.date ? `latest, ${tick.label}` : tick.label;
  return total > 0 ? `${when}: ${tick.count} of ${total} metros have a value` : when;
}

// the as of control: a calendar axis with one tick per period, filled where
// the metric has values. the current tick is the one tab stop; arrows move
// between the available ones and play steps through them once
export function Timeline({ def, metros, period, available, onPeriodChange }: Props) {
  const model = useMemo(() => buildTimeline(def, metros), [def, metros]);
  const [playing, setPlaying] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const canPlay = available.length > 1;

  // a new metric ends the run
  useEffect(() => {
    setPlaying(false);
  }, [def.id]);

  // each step schedules the one after it; the run ends past the last period
  useEffect(() => {
    if (!playing) return;
    const id = window.setTimeout(() => {
      const next = nextPeriod(period, available);
      if (next) onPeriodChange(next);
      else setPlaying(false);
    }, PLAY_MS);
    return () => window.clearTimeout(id);
  }, [playing, period, available, onPeriodChange]);

  const togglePlay = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (!canPlay) return;
    onPeriodChange(available[0]);
    setPlaying(true);
  };

  const move = (target: Period | null) => {
    if (!target) return;
    setPlaying(false);
    onPeriodChange(target);
    root.current?.querySelector<HTMLButtonElement>(`[data-period="${target}"]`)?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const keys: Record<string, () => Period | null> = {
      ArrowRight: () => nextPeriod(period, available),
      ArrowLeft: () => prevPeriod(period, available),
      Home: () => available[0] ?? null,
      End: () => available[available.length - 1] ?? null,
    };
    const pick = keys[e.key];
    if (!pick) return;
    e.preventDefault();
    move(pick());
  };

  return (
    <div className="timeline-block">
      <div className="timeline-head">
        <span className="label" id="period-label">as of</span>
        <button
          type="button"
          className="play"
          aria-pressed={playing}
          aria-label={playing ? "stop stepping through the periods" : "play through the periods"}
          title={canPlay ? "steps from the first period to the last, about a second each" : "needs two or more periods"}
          disabled={!canPlay}
          onClick={togglePlay}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            {playing ? <rect x="1.5" y="1.5" width="7" height="7" rx="1" /> : <polygon points="2,1 9,5 2,9" />}
          </svg>
          {playing ? "stop" : "play"}
        </button>
      </div>
      <div ref={root} className="timeline" role="group" aria-labelledby="period-label" onKeyDown={onKeyDown}>
        <div className="axis" aria-hidden="true">
          {model.marks.map((m) => (
            <span key={m.year} className="mark" style={{ left: pct(m.t) }} />
          ))}
        </div>
        {model.span && (
          <>
            <div
              className="span"
              style={{ left: pct(model.span.t0), width: pct(model.span.t1 - model.span.t0) }}
              title={`${def.label}: the change over these years`}
            />
            <span className="span-year" style={{ left: pct(model.span.t0) }}>{model.span.from}</span>
            <span className="span-year" style={{ left: pct(model.span.t1) }}>{model.span.to}</span>
          </>
        )}
        {model.ticks.map((tick) => {
          const current = tick.period === period;
          const count = tick.available ? `${tick.count} metros` : "not published";
          const isLatest = tick.period === "latest";
          const name = isLatest && tick.date ? `latest, ${tick.label}` : tick.label;
          return (
            <button
              type="button"
              key={tick.period}
              className={`tick ${tick.available ? "filled" : "hollow"}${current ? " current" : ""}`}
              data-period={tick.period}
              style={{ left: pct(tick.t) }}
              aria-pressed={current}
              aria-disabled={!tick.available}
              aria-label={`${name}, ${count}`}
              tabIndex={current ? 0 : -1}
              title={tickTitle(tick, metros.length)}
              onClick={() => tick.available && move(tick.period)}
            >
              <span className="dot" aria-hidden="true" />
              <span className="lbl" style={{ marginTop: tick.row ? 28 : 3 }}>
                <span className="when">{isLatest ? "latest" : tick.label}</span>
                {isLatest && tick.date && <span className="date">{tick.label}</span>}
                <span className="n">{count}</span>
              </span>
            </button>
          );
        })}
      </div>
      {def.periods.length === 0 && <p className="mode-note">a change between the shaded years, not a single period</p>}
      {def.periods.length > 0 && available.length === 0 && <p className="mode-note">no period carries a value in this data</p>}
    </div>
  );
}
