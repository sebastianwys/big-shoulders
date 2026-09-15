import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SAMPLE } from "../lib/data";
import { nationalIndicators } from "../lib/indicators";
import type { Indicator } from "../types";
import { Header } from "./Header";
import { IndicatorChart } from "./IndicatorChart";
import { IndicatorDetail, NationalStrip } from "./NationalStrip";

// there is no dom in this suite, so the markup is read as a string. it
// proves the text and the aria wiring, not the clicking
const html = (node: ReactElement) => renderToStaticMarkup(node);
const count = (markup: string, needle: string) => markup.split(needle).length - 1;

const indicators = nationalIndicators(SAMPLE);
const byId = (id: string) => indicators.find((i) => i.id === id)!;
const cpi = byId("cpi");
const rate = SAMPLE.national.mortgage_rate;

const one: Indicator = { ...cpi, id: "solo", label: "One month only", history: cpi.history.slice(-1) };
const flat: Indicator = { ...cpi, id: "flat", label: "Held steady", change_12m: 0 };

describe("the strip", () => {
  const markup = html(<NationalStrip indicators={indicators} />);

  it("renders nothing when the build carries no indicators", () => {
    expect(html(<NationalStrip indicators={[]} />)).toBe("");
  });

  it("puts one tile per indicator in the fixed group order", () => {
    expect(count(markup, 'class="ind-tile')).toBe(13);
    expect(markup.indexOf(">Prices<")).toBeLessThan(markup.indexOf(">Rates<"));
    expect(markup.indexOf(">Rates<")).toBeLessThan(markup.indexOf(">Consumers<"));
    expect(markup.indexOf("CPI, all items")).toBeLessThan(markup.indexOf("Fed funds rate"));
    expect(markup.indexOf("Fed funds rate")).toBeLessThan(markup.indexOf("Consumer sentiment"));
  });

  it("associates each group of tiles with its label", () => {
    for (const group of ["prices", "rates", "consumers"]) {
      expect(markup).toContain(`<span class="group-label" id="indicator-group-${group}">`);
      expect(markup).toContain(`aria-labelledby="indicator-group-${group}"`);
    }
    expect(count(markup, 'role="group"')).toBe(3);
  });

  it("makes every tile a button that controls the one detail row", () => {
    expect(count(markup, 'aria-controls="national-indicator-detail"')).toBe(13);
    expect(count(markup, 'aria-expanded="false"')).toBe(13);
    expect(count(markup, 'id="national-indicator-detail"')).toBe(1);
    expect(markup).toContain('id="indicator-tile-core_cpi"');
    expect(markup).toContain('aria-label="CPI, all items, 2.9% in Aug 2026, down 0.2 pts over twelve months"');
  });

  it("reads the value, the month and the change on the face of a tile", () => {
    expect(markup).toContain('<span class="value">2.9%</span>');
    expect(markup).toContain(">Aug 2026<");
    expect(markup).toContain('<span class="chip down">-0.2 pts<span class="word">down</span></span>');
    expect(markup).toContain('<span class="chip up">+0.1 pts<span class="word">up</span></span>');
  });

  it("prints no change rather than a signed zero", () => {
    const steady = html(<NationalStrip indicators={[flat]} />);
    expect(steady).toContain('<span class="chip flat">no change</span>');
    expect(steady).not.toContain("+0.0");
  });

  it("gives every sparkline a title and a label, and draws none below two points", () => {
    expect(count(markup, 'class="ind-spark"')).toBe(13);
    expect(markup).toContain('aria-label="CPI, all items, monthly, Sep 2023 to Aug 2026"');
    expect(count(markup, "<title>")).toBe(13);
    const single = html(<NationalStrip indicators={[one]} />);
    expect(single).toContain("One month only");
    expect(single).not.toContain("ind-spark");
    expect(single).not.toContain("<path");
  });

  it("leaves the detail row empty until a tile is opened", () => {
    expect(markup).toContain('<div class="strip-detail" id="national-indicator-detail"></div>');
    expect(markup).not.toContain("ind-detail");
  });
});

describe("the detail row", () => {
  const markup = html(<IndicatorDetail indicator={cpi} width={600} onClose={() => undefined} />);

  it("names itself and shows the value it was opened at", () => {
    expect(markup).toContain('role="region" aria-label="CPI, all items, the full history"');
    expect(markup).toContain("2.9%");
    expect(markup).toContain(" in Aug 2026");
    expect(markup).toContain('aria-label="close the indicator detail"');
  });

  it("carries the note, the provider and the months shown", () => {
    expect(markup).toContain("The change in consumer prices over the last twelve months.");
    expect(markup).toContain("BLS via FRED, monthly, Sep 2023 to Aug 2026");
  });

  it("draws the full history as one keyboard reachable chart", () => {
    expect(markup).toContain('width="600" height="100"');
    expect(markup).toContain('tabindex="0"');
    expect(markup).toContain('aria-label="CPI, all items, monthly, Sep 2023 to Aug 2026, arrow keys read out each month"');
    expect(markup).toContain("<title>CPI, all items, monthly, Sep 2023 to Aug 2026</title>");
    expect(count(markup, "<path")).toBe(1);
  });

  it("says so instead of drawing a broken line for one point", () => {
    expect(html(<IndicatorChart indicator={one} />)).toBe('<p class="muted">no monthly history</p>');
  });
});

describe("the header", () => {
  it("drops the standalone rate stat once a tile carries the same rate", () => {
    const markup = html(<Header rate={rate} sample={false} count={410} indicators={indicators} updated="2026-09-15" />);
    expect(markup).not.toContain('class="stat"');
    expect(markup).toContain("30-year mortgage rate");
    expect(markup).toContain("national figures as of 2026-09-15");
    expect(markup).toContain("410 U.S. metros");
  });

  it("keeps the stat exactly as it is when the build has no indicators", () => {
    const markup = html(<Header rate={rate} sample={false} count={410} />);
    expect(markup).toContain('<div class="stat" aria-label="national 30 year mortgage rate">');
    expect(markup).toContain('<span class="value">6.76%</span>');
    expect(markup).toContain("as of 2026-09-10");
    expect(markup).not.toContain("ind-tile");
    expect(markup).not.toContain("strip");
  });

  it("keeps the stat when the block is there but carries no mortgage tile", () => {
    const markup = html(<Header rate={rate} sample={false} indicators={[cpi]} />);
    expect(markup).toContain('class="stat"');
    expect(count(markup, 'class="ind-tile')).toBe(1);
  });
});
